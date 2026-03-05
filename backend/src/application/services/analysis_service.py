"""Analysis service orchestrator."""
import asyncio
import json
import logging
import traceback
from pathlib import Path
from typing import Any, Optional
from domain.entities.analysis import Analysis
from domain.entities.analysis_settings import SOURCE_CODE_EXTENSIONS
from domain.entities.repository import Repository
from domain.entities.analysis_event import AnalysisEvent
from domain.interfaces.repositories import (
    IRepository,
    IAnalysisEventRepository,
)
from domain.exceptions.domain_exceptions import NotFoundError
from infrastructure.analysis.structure_analyzer import StructureAnalyzer
from infrastructure.persistence.analysis_settings_repository import (
    IgnoredDirsRepository,
    LibraryCapabilitiesRepository,
)
from infrastructure.storage.storage_interface import IStorage
from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
from application.services.analysis_data_collector import analysis_data_collector
from infrastructure.events.event_bus import publish as _publish_event


class AnalysisService:
    """Service for orchestrating repository analysis.
    
    Uses RAG-based retrieval for comprehensive codebase analysis:
    1. Index repository: Generate embeddings for all code files
    2. Phased analysis: For each phase, retrieve semantically relevant code
    3. Synthesis: Generate comprehensive blueprint from all phases
    """

    def __init__(
        self,
        analysis_repo: IRepository[Analysis, str],
        repository_repo: IRepository[Repository, str],
        event_repo: IAnalysisEventRepository,
        structure_analyzer: StructureAnalyzer,
        persistent_storage: IStorage,
        phased_blueprint_generator: PhasedBlueprintGenerator,
        db_client=None,
        intent_layer_service=None,
    ):
        """Initialize analysis service."""
        self._analysis_repo = analysis_repo
        self._repository_repo = repository_repo
        self._event_repo = event_repo
        self._structure_analyzer = structure_analyzer
        self._persistent_storage = persistent_storage
        self._phased_blueprint_generator = phased_blueprint_generator
        self._db_client = db_client
        self._intent_layer_service = intent_layer_service
        # Set progress callback on generator to use our logging
        self._phased_blueprint_generator._progress_callback = self._log_event

    _logger = logging.getLogger("analysis_service")

    async def _log_event(self, analysis_id: str, event_type: str, message: str, details: dict | None = None) -> None:
        """Log an analysis event. Never raises — falls back to stderr on DB failure."""
        try:
            event = AnalysisEvent.create(analysis_id, event_type, message, details)
            await self._event_repo.add(event)
        except Exception as log_err:
            # DB write failed — print to stderr so it still appears in server logs
            self._logger.error(
                "[%s] Failed to write event to DB (type=%s): %s | Original message: %s",
                analysis_id[:8], event_type, log_err, message,
            )
        # Push to in-memory event bus for real-time SSE delivery
        try:
            from infrastructure.events.event_bus import publish
            await publish(analysis_id, {"event": "log", "type": event_type, "message": message})
        except Exception:
            pass

    async def start_analysis(
        self,
        repository_id: str,
        prompt_config: dict[str, str] | None = None,
    ) -> Analysis:
        """Start analysis for a repository."""
        # Get repository
        repo = await self._repository_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundError("Repository", repository_id)

        # Create analysis
        analysis = Analysis.create(repository_id)
        analysis = await self._analysis_repo.add(analysis)

        # Log start event
        await self._log_event(analysis.id, "PHASE_START", f"Starting analysis for {repo.full_name}")

        # Start analysis (will be run in background worker)
        analysis.start()
        await self._analysis_repo.update(analysis)

        return analysis

    async def run_analysis(
        self,
        analysis_id: str,
        repo_path: Path,
        token: str,
        prompt_config: dict[str, str] | None = None,
    ) -> None:
        """Run the full analysis pipeline."""
        analysis = await self._analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise NotFoundError("Analysis", analysis_id)

        try:
            # Load analysis settings from DB (no DB = no filtering)
            discovery_ignored_dirs: set[str] = set()
            library_capabilities: dict[str, dict] = {}
            if self._db_client:
                try:
                    dirs_repo = IgnoredDirsRepository(db=self._db_client)
                    dir_rows = await dirs_repo.get_all()
                    if dir_rows:
                        discovery_ignored_dirs = {d.directory_name for d in dir_rows}
                    lib_repo = LibraryCapabilitiesRepository(db=self._db_client)
                    lib_rows = await lib_repo.get_all()
                    if lib_rows:
                        library_capabilities = {
                            lib.library_name: {"capabilities": lib.capabilities, "ecosystem": lib.ecosystem}
                            for lib in lib_rows
                        }
                except Exception as settings_err:
                    self._logger.warning("[%s] Failed to load analysis settings from DB: %s", analysis_id[:8], settings_err)

            # Publish initial status to event bus
            await _publish_event(analysis_id, {"event": "status", "status": "analyzing", "progress": 10})

            # Phase 1: Structure scan (data extraction only)
            await self._log_event(analysis_id, "PHASE_START", "Phase 1: Scanning file structure")
            await self._log_event(analysis_id, "INFO", f"Analyzing repository structure at: {repo_path}")
            # Verify repo_path exists and resolve it
            repo_path_obj = Path(repo_path) if not isinstance(repo_path, Path) else repo_path
            repo_path_obj = repo_path_obj.resolve()  # Resolve to absolute path
            
            await self._log_event(analysis_id, "INFO", f"Repository path (resolved): {repo_path_obj}")
            
            if not repo_path_obj.exists():
                await self._log_event(analysis_id, "ERROR", f"Repository path does not exist: {repo_path_obj}")
            elif not repo_path_obj.is_dir():
                await self._log_event(analysis_id, "ERROR", f"Repository path is not a directory: {repo_path_obj}")
            else:
                # Count items in directory for debugging
                try:
                    items = list(repo_path_obj.iterdir())
                    await self._log_event(analysis_id, "INFO", f"Repository directory contains {len(items)} items at root level")
                    
                    # List first few items for debugging
                    all_items = [item.name for item in items]
                    visible_items = [item.name for item in items if not item.name.startswith('.')][:10]
                    
                    if all_items:
                        await self._log_event(analysis_id, "INFO", f"All items in root (first 10): {', '.join(all_items[:10])}")
                    if visible_items:
                        await self._log_event(analysis_id, "INFO", f"Visible items in root: {', '.join(visible_items[:5])}")
                    else:
                        await self._log_event(analysis_id, "WARNING", f"No visible items found in root directory. All {len(items)} items are hidden (start with '.')")
                        
                        # Check if .git exists (should always be there after clone)
                        git_dir = repo_path_obj / ".git"
                        if git_dir.exists():
                            await self._log_event(analysis_id, "INFO", ".git directory exists - repository was cloned successfully")
                        else:
                            await self._log_event(analysis_id, "ERROR", ".git directory does NOT exist - repository may not have been cloned correctly!")
                except Exception as e:
                    await self._log_event(analysis_id, "ERROR", f"Cannot read repository directory: {str(e)}")
                    import traceback
                    await self._log_event(analysis_id, "ERROR", f"Traceback: {traceback.format_exc()}")
            
            analysis.update_progress(10)
            await self._analysis_repo.update(analysis)
            
            # Call structure analyzer with detailed logging
            await self._log_event(analysis_id, "INFO", f"Calling structure analyzer with path: {repo_path_obj}")
            await self._log_event(analysis_id, "INFO", f"Path exists: {repo_path_obj.exists()}, is_dir: {repo_path_obj.is_dir() if repo_path_obj.exists() else False}")
            
            try:
                structure_data = await self._structure_analyzer.analyze(repo_path_obj, discovery_ignored_dirs=discovery_ignored_dirs)
                await self._log_event(analysis_id, "INFO", f"Structure analyzer returned data: {bool(structure_data)}")
                
                if structure_data:
                    await self._log_event(analysis_id, "INFO", f"Structure data keys: {list(structure_data.keys())}")
                else:
                    await self._log_event(analysis_id, "ERROR", "Structure analyzer returned None or empty data!")
            except Exception as e:
                await self._log_event(analysis_id, "ERROR", f"Structure analyzer raised exception: {str(e)}")
                import traceback
                await self._log_event(analysis_id, "ERROR", f"Traceback: {traceback.format_exc()}")
                raise
            
            # Count files and directories from file_tree
            file_tree = structure_data.get("file_tree", []) if structure_data else []
            await self._log_event(analysis_id, "INFO", f"File tree from structure_data: {len(file_tree)} items")
            
            if file_tree:
                await self._log_event(analysis_id, "INFO", f"First 5 items in file_tree: {[item.get('path', 'unknown') for item in file_tree[:5]]}")
            
            file_count = len([node for node in file_tree if node.get("type") == "file"])
            dir_count = len([node for node in file_tree if node.get("type") == "directory"])
            await self._log_event(analysis_id, "INFO", f"Structure scan complete: {file_count} files, {dir_count} directories")
            await self._log_event(analysis_id, "PHASE_END", "Phase 1 complete: File structure indexed")

            # Phase 2: Prepare data for phased analysis
            await self._log_event(analysis_id, "PHASE_START", "Phase 2: Preparing repository data")
            analysis.update_progress(20)
            await self._analysis_repo.update(analysis)
            
            # Validate structure_data is still valid before Phase 2
            if not structure_data:
                await self._log_event(analysis_id, "ERROR", "structure_data is None at start of Phase 2!")
                raise ValueError("structure_data is None - structure analysis failed")
            
            file_tree_from_data = structure_data.get("file_tree", [])
            await self._log_event(analysis_id, "INFO", f"Phase 2: structure_data has {len(file_tree_from_data)} items in file_tree")
            
            if not file_tree_from_data:
                await self._log_event(analysis_id, "ERROR", "file_tree is empty at start of Phase 2!")
                await self._log_event(analysis_id, "ERROR", f"structure_data keys: {list(structure_data.keys())}")
                await self._log_event(analysis_id, "ERROR", f"structure_data['file_tree'] type: {type(file_tree_from_data)}")
                raise ValueError("file_tree is empty - structure analysis returned no files")
            
            # Extract file tree
            await self._log_event(analysis_id, "INFO", "Formatting file tree structure...")
            file_tree = self._format_file_tree(structure_data)
            await self._log_event(analysis_id, "INFO", f"Formatted file tree length: {len(file_tree.split(chr(10))) if file_tree else 0} lines")
            
            # Extract dependencies
            await self._log_event(analysis_id, "INFO", "Extracting dependencies from package files...")
            dependencies = await self._extract_dependencies(repo_path_obj, discovery_ignored_dirs=discovery_ignored_dirs)
            # Count dependency files found (each "**filename:**" indicates a file)
            if dependencies and "No dependency files found" not in dependencies:
                # Count occurrences of "**" pattern (each file has "**path:**")
                dep_count = dependencies.count("**") // 2
            else:
                dep_count = 0
            await self._log_event(analysis_id, "INFO", f"Dependencies extracted: {dep_count} dependency files found")
            
            # Extract config files
            await self._log_event(analysis_id, "INFO", "Extracting configuration files...")
            config_files = await self._extract_config_files(repo_path_obj, discovery_ignored_dirs=discovery_ignored_dirs)
            await self._log_event(analysis_id, "INFO", f"Configuration files extracted: {len(config_files)} files")
            
            # Extract code samples
            await self._log_event(analysis_id, "INFO", "Extracting representative code samples...")
            code_samples = await self._extract_code_samples(repo_path_obj, structure_data, discovery_ignored_dirs=discovery_ignored_dirs)
            await self._log_event(analysis_id, "INFO", f"Code samples extracted: {len(code_samples)} files")
            
            # Capture gathered data for analysis data view
            await analysis_data_collector.capture_gathered_data(analysis_id, {
                "file_tree_raw": file_tree,
                "dependencies_raw": dependencies,
                "config_files": config_files,
                "code_samples": code_samples,
                "rag_indexing": {} # Will be updated by RAG retriever later if indexing happens
            })
            
            await self._log_event(analysis_id, "PHASE_END", "Phase 2 complete: Repository data prepared")

            # Phase 3: Phased blueprint generation (AI-driven)
            await self._log_event(analysis_id, "PHASE_START", "Phase 3: Running phased AI analysis")
            analysis.update_progress(30)
            await self._analysis_repo.update(analysis)
            await _publish_event(analysis_id, {"event": "status", "status": "analyzing", "progress": 30})
            
            # Get repository name
            repo = await self._repository_repo.get_by_id(analysis.repository_id)
            repo_name = repo.full_name if repo else analysis.repository_id
            
            # Cross-reference detected dependencies with library capability map
            provided_capabilities: dict[str, list[str]] = {}
            if dependencies and "No dependency files found" not in dependencies:
                dep_text_lower = dependencies.lower()
                for lib_key, lib_info in library_capabilities.items():
                    if lib_key.lower() in dep_text_lower:
                        for cap in lib_info.get("capabilities", []):
                            if cap not in provided_capabilities:
                                provided_capabilities[cap] = []
                            provided_capabilities[cap].append(
                                f"{lib_key} (via {lib_info.get('ecosystem', 'unknown')})"
                            )

            if provided_capabilities:
                await self._log_event(
                    analysis_id, "INFO",
                    f"Detected library capabilities: {', '.join(provided_capabilities.keys())}",
                )

            # Generate Backend Blueprint (dual format: JSON + Markdown)
            await self._log_event(analysis_id, "INFO", "Starting backend architecture analysis...")
            blueprint_result = await self._phased_blueprint_generator.generate(
                repo_path=repo_path_obj,
                repository_name=repo_name,
                repository_id=analysis.repository_id,
                analysis_id=analysis_id,
                file_tree=file_tree,
                dependencies=dependencies,
                config_files=config_files,
                code_samples=code_samples,
                blueprint_type="backend",
                discovery_ignored_dirs=discovery_ignored_dirs,
                provided_capabilities=provided_capabilities,
                structure_data=structure_data,
            )
            
            # Validate blueprint was generated (returns dict with "structured" and optionally "markdown")
            if not blueprint_result:
                raise ValueError("Backend blueprint generation returned None or empty result")
            if not isinstance(blueprint_result, dict):
                raise ValueError(f"Backend blueprint is not a dict, got: {type(blueprint_result)}")
            
            structured_blueprint = blueprint_result.get("structured", {})
            
            if not structured_blueprint:
                raise ValueError("Backend structured blueprint is empty")
            
            await self._log_event(
                analysis_id, "INFO",
                f"Backend blueprint generated: "
                f"{len(json.dumps(structured_blueprint))} chars JSON"
            )
            analysis.update_progress(90)
            await self._analysis_repo.update(analysis)
            
            await self._log_event(analysis_id, "PHASE_END", "Phase 3 complete: Backend blueprint generated")

            # Phase 4: Save structured JSON blueprint (single source of truth)
            await self._log_event(analysis_id, "PHASE_START", "Phase 4: Saving blueprint")
            analysis.update_progress(95)
            await self._analysis_repo.update(analysis)
            
            json_blueprint_path = f"blueprints/{analysis.repository_id}/blueprint.json"
            try:
                json_content = json.dumps(structured_blueprint, indent=2, ensure_ascii=False)
                await self._persistent_storage.save(json_blueprint_path, json_content)
                await self._log_event(analysis_id, "INFO", f"Structured blueprint saved to: {json_blueprint_path}")
                
                # Verify the file was actually saved
                file_exists = await self._persistent_storage.exists(json_blueprint_path)
                if not file_exists:
                    error_msg = f"WARNING: Blueprint file not found after save at: {json_blueprint_path}"
                    await self._log_event(analysis_id, "ERROR", error_msg)
                    raise FileNotFoundError(error_msg)
                else:
                    await self._log_event(analysis_id, "INFO", f"Verified: Blueprint file exists at: {json_blueprint_path}")
            except Exception as save_error:
                await self._log_event(analysis_id, "ERROR", f"Failed to save blueprint: {str(save_error)}")
                import traceback
                await self._log_event(analysis_id, "ERROR", f"Traceback: {traceback.format_exc()}")
                raise
            
            # Save phase outputs alongside blueprint.json
            phase_outputs = blueprint_result.get("phase_outputs", {})
            if phase_outputs:
                for phase_name, phase_data in phase_outputs.items():
                    if phase_data:  # Skip empty phases
                        phase_path = f"blueprints/{analysis.repository_id}/{phase_name}.json"
                        try:
                            phase_content = phase_data if isinstance(phase_data, str) else json.dumps(phase_data, indent=2, ensure_ascii=False)
                            await self._persistent_storage.save(phase_path, phase_content)
                        except Exception as phase_save_err:
                            self._logger.warning("[%s] Failed to save phase output '%s': %s", analysis_id[:8], phase_name, phase_save_err)
                await self._log_event(analysis_id, "INFO", f"Phase outputs saved: {list(phase_outputs.keys())}")

            await self._log_event(analysis_id, "PHASE_END", "Phase 4 complete: Blueprint saved")

            # Phase 6: Copy repository to persistent storage
            try:
                await self._log_event(analysis_id, "PHASE_START", "Phase 6: Copying repository to storage")
                from application.services.source_file_collector import SourceFileCollector
                collector = SourceFileCollector()
                storage_base = Path(self._persistent_storage._base_path)
                dest_dir = storage_base / "repos" / str(analysis.repository_id)
                manifest = await asyncio.to_thread(
                    collector.copy_repo,
                    temp_repo_dir=repo_path_obj,
                    dest_dir=dest_dir,
                    ignored_dirs=discovery_ignored_dirs,
                )
                await self._log_event(
                    analysis_id, "INFO",
                    f"Copied {manifest.get('file_count', 0)} files "
                    f"({manifest.get('total_size', 0)} bytes) to persistent storage"
                )
                await self._log_event(analysis_id, "PHASE_END", "Phase 6 complete: Repository copied")
            except Exception as collect_error:
                await self._log_event(
                    analysis_id, "WARNING",
                    f"Repository copy failed (non-fatal): {str(collect_error)}"
                )

            # Phase 7: Intent layer — per-folder CLAUDE.md with AI enrichment
            if self._intent_layer_service:
                try:
                    await self._log_event(analysis_id, "PHASE_START", "Phase 7: Generating per-folder CLAUDE.md (intent layer)")

                    async def _il_progress(msg: str) -> None:
                        await self._log_event(analysis_id, "INFO", f"[Intent Layer] {msg}")

                    il_output = await self._intent_layer_service.preview(
                        source_repo_id=analysis.repository_id,
                        progress_callback=_il_progress,
                    )
                    # Save the commit-ready file tree to storage
                    for rel_path, content in il_output.claude_md_files.items():
                        storage_path = f"blueprints/{analysis.repository_id}/intent_layer/{rel_path}"
                        await self._persistent_storage.save(storage_path, content)

                    await self._log_event(
                        analysis_id, "INFO",
                        f"Intent layer complete: {il_output.folder_count} folders, "
                        f"{il_output.total_ai_calls} AI calls, "
                        f"{il_output.generation_time_seconds}s"
                    )
                    await self._log_event(analysis_id, "PHASE_END", "Phase 7 complete: Intent layer generated")
                except Exception as il_error:
                    await self._log_event(
                        analysis_id, "WARNING",
                        f"Intent layer generation failed (non-fatal): {str(il_error)}"
                    )

            # Complete analysis
            await self._log_event(analysis_id, "INFO", "Analysis completed successfully")
            analysis.update_progress(100)
            analysis.complete()
            await self._analysis_repo.update(analysis)
            await _publish_event(analysis_id, {"event": "complete", "status": "completed", "progress": 100})

        except Exception as e:
            tb = traceback.format_exc()
            self._logger.error("[%s] Analysis failed: %s\n%s", analysis_id[:8], e, tb)
            await self._log_event(analysis_id, "ERROR", f"Analysis failed: {str(e)}")
            await self._log_event(analysis_id, "ERROR", f"Traceback:\n{tb[-1500:]}")
            try:
                analysis.fail(str(e))
                await self._analysis_repo.update(analysis)
                await _publish_event(analysis_id, {"event": "complete", "status": "failed", "error_message": str(e)})
            except Exception as status_err:
                self._logger.error("[%s] Failed to mark analysis as failed: %s", analysis_id[:8], status_err)
            raise
        finally:
            # Release embedding model to free ~400 MB
            try:
                from infrastructure.analysis.shared_embedder import release_model
                release_model()
            except Exception:
                pass

    def _format_file_tree(self, structure_data: dict[str, Any]) -> str:
        """Format structure data as a compressed file tree."""
        if not structure_data or "file_tree" not in structure_data:
            return "No structure data available"
        
        file_tree = structure_data["file_tree"]
        if not file_tree:
            return "No files found in repository"
        
        lines = []
        # Format first 150 items (mix of files and directories)
        for node in file_tree[:150]:
            node_type = node.get("type", "file")
            node_path = node.get("path", node.get("name", "unknown"))
            icon = "📁" if node_type == "directory" else "📄"
            lines.append(f"{icon} {node_path}")
        
        if len(file_tree) > 150:
            lines.append(f"... and {len(file_tree) - 150} more items")
        
        return "\n".join(lines)

    def _extract_dependencies_sync(self, repo_path: Path, discovery_ignored_dirs: set[str] | None = None) -> str:
        """Extract dependencies from package files recursively (sync I/O)."""
        dependencies = []

        ignore_patterns = discovery_ignored_dirs or set()

        # Find all requirements.txt files recursively
        for requirements_file in repo_path.rglob("requirements.txt"):
            # Skip if in ignored directory
            if any(part in ignore_patterns for part in requirements_file.relative_to(repo_path).parts):
                continue

            try:
                content = requirements_file.read_text(encoding="utf-8", errors="ignore")
                # Get relative path from repo root
                rel_path = requirements_file.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all package.json files recursively
        for package_json in repo_path.rglob("package.json"):
            # Skip if in ignored directory
            if any(part in ignore_patterns for part in package_json.relative_to(repo_path).parts):
                continue

            try:
                content = package_json.read_text(encoding="utf-8", errors="ignore")
                # Get relative path from repo root
                rel_path = package_json.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```json\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all pyproject.toml files recursively (Python projects using modern tooling)
        for pyproject_toml in repo_path.rglob("pyproject.toml"):
            if any(part in ignore_patterns for part in pyproject_toml.relative_to(repo_path).parts):
                continue

            try:
                content = pyproject_toml.read_text(encoding="utf-8", errors="ignore")
                rel_path = pyproject_toml.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```toml\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all Gemfile files recursively (Ruby projects)
        for gemfile in repo_path.rglob("Gemfile"):
            if any(part in ignore_patterns for part in gemfile.relative_to(repo_path).parts):
                continue

            try:
                content = gemfile.read_text(encoding="utf-8", errors="ignore")
                rel_path = gemfile.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```ruby\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all Cargo.toml files recursively (Rust projects)
        for cargo_toml in repo_path.rglob("Cargo.toml"):
            if any(part in ignore_patterns for part in cargo_toml.relative_to(repo_path).parts):
                continue

            try:
                content = cargo_toml.read_text(encoding="utf-8", errors="ignore")
                rel_path = cargo_toml.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```toml\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all Podfile files recursively (iOS CocoaPods)
        for podfile in repo_path.rglob("Podfile"):
            if any(part in ignore_patterns for part in podfile.relative_to(repo_path).parts):
                continue
            try:
                content = podfile.read_text(encoding="utf-8", errors="ignore")
                rel_path = podfile.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```ruby\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all Package.swift files recursively (iOS SPM)
        for pkg_swift in repo_path.rglob("Package.swift"):
            if any(part in ignore_patterns for part in pkg_swift.relative_to(repo_path).parts):
                continue
            try:
                content = pkg_swift.read_text(encoding="utf-8", errors="ignore")
                rel_path = pkg_swift.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```swift\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all Cartfile files recursively (iOS Carthage)
        for cartfile in repo_path.rglob("Cartfile"):
            if any(part in ignore_patterns for part in cartfile.relative_to(repo_path).parts):
                continue
            try:
                content = cartfile.read_text(encoding="utf-8", errors="ignore")
                rel_path = cartfile.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all build.gradle files recursively (Android Gradle)
        for gradle_file in repo_path.rglob("build.gradle"):
            if any(part in ignore_patterns for part in gradle_file.relative_to(repo_path).parts):
                continue
            try:
                content = gradle_file.read_text(encoding="utf-8", errors="ignore")
                rel_path = gradle_file.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```groovy\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all build.gradle.kts files recursively (Android Gradle Kotlin DSL)
        for gradle_kts in repo_path.rglob("build.gradle.kts"):
            if any(part in ignore_patterns for part in gradle_kts.relative_to(repo_path).parts):
                continue
            try:
                content = gradle_kts.read_text(encoding="utf-8", errors="ignore")
                rel_path = gradle_kts.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```kotlin\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all settings.gradle* files recursively (Android module declarations)
        for settings_gradle in repo_path.rglob("settings.gradle*"):
            if any(part in ignore_patterns for part in settings_gradle.relative_to(repo_path).parts):
                continue
            try:
                content = settings_gradle.read_text(encoding="utf-8", errors="ignore")
                rel_path = settings_gradle.relative_to(repo_path)
                lang = "kotlin" if str(rel_path).endswith(".kts") else "groovy"
                dependencies.append(f"**{rel_path}:**\n```{lang}\n{content[:1000]}\n```")
            except Exception:
                continue

        # Find all go.mod files recursively (Go projects)
        for go_mod in repo_path.rglob("go.mod"):
            if any(part in ignore_patterns for part in go_mod.relative_to(repo_path).parts):
                continue

            try:
                content = go_mod.read_text(encoding="utf-8", errors="ignore")
                rel_path = go_mod.relative_to(repo_path)
                dependencies.append(f"**{rel_path}:**\n```\n{content[:1000]}\n```")
            except Exception:
                continue

        return "\n\n".join(dependencies) if dependencies else "No dependency files found"

    async def _extract_dependencies(self, repo_path: Path, discovery_ignored_dirs: set[str] | None = None) -> str:
        """Extract dependencies from package files recursively."""
        return await asyncio.to_thread(self._extract_dependencies_sync, repo_path, discovery_ignored_dirs)

    def _extract_config_files_sync(self, repo_path: Path, discovery_ignored_dirs: set[str] | None = None) -> dict[str, str]:
        """Extract key configuration files recursively (sync I/O)."""
        config_files = {}

        ignore_patterns = discovery_ignored_dirs or set()

        # Common configuration file patterns (exact matches)
        exact_config_patterns = [
            # Environment files
            ".env.example", ".env.sample", ".env.template",
            # Docker
            "docker-compose.yml", "docker-compose.yaml", "Dockerfile", ".dockerignore",
            # Firebase
            "firebase.json", ".firebaserc", "firestore.rules",
            # Deployment
            "vercel.json", "netlify.toml", ".vercelignore", ".netlifyignore",
            # Python config
            "config.py", "settings.py", "setup.py", "setup.cfg", "tox.ini", "pytest.ini",
            # TypeScript/JavaScript config
            "tsconfig.json", "jsconfig.json",
            # CI/CD
            ".gitlab-ci.yml",
            # Mobile
            "AndroidManifest.xml", "proguard-rules.pro", "gradle.properties",
            "Info.plist", "Podfile.lock",
            # Other common config files
            ".editorconfig", ".gitignore",
        ]

        # Patterns with extensions (search for base name with any extension)
        config_base_names = [
            # Build tools
            "webpack.config", "vite.config", "next.config", "nuxt.config",
            "rollup.config", "esbuild.config", "swc.config",
            # CSS config
            "tailwind.config", "postcss.config",
            # Testing
            "jest.config", "vitest.config",
            # Linting/Formatting
            ".eslintrc", ".prettierrc",
            # TypeScript config variants
            "tsconfig",
            # Mobile build files
            "build.gradle", "settings.gradle",
        ]

        # Extension patterns to check
        config_extensions = [".json", ".js", ".ts", ".mjs", ".cjs", ".yml", ".yaml", ".toml"]

        # Search for exact patterns
        for pattern in exact_config_patterns:
            for config_file in repo_path.rglob(pattern):
                # Skip if in ignored directory
                if any(part in ignore_patterns for part in config_file.relative_to(repo_path).parts):
                    continue

                try:
                    content = config_file.read_text(encoding="utf-8", errors="ignore")
                    rel_path = config_file.relative_to(repo_path)
                    config_files[str(rel_path)] = content[:1000]
                except Exception:
                    continue

        # Search for base names with various extensions
        for base_name in config_base_names:
            for ext in config_extensions:
                pattern = f"{base_name}{ext}"
                for config_file in repo_path.rglob(pattern):
                    if any(part in ignore_patterns for part in config_file.relative_to(repo_path).parts):
                        continue

                    try:
                        content = config_file.read_text(encoding="utf-8", errors="ignore")
                        rel_path = config_file.relative_to(repo_path)
                        config_files[str(rel_path)] = content[:1000]
                    except Exception:
                        continue

        # Search for CI/CD workflow files
        for workflow_file in (repo_path / ".github" / "workflows").rglob("*.yml"):
            if any(part in ignore_patterns for part in workflow_file.relative_to(repo_path).parts):
                continue
            try:
                content = workflow_file.read_text(encoding="utf-8", errors="ignore")
                rel_path = workflow_file.relative_to(repo_path)
                config_files[str(rel_path)] = content[:1000]
            except Exception:
                pass

        for workflow_file in (repo_path / ".github" / "workflows").rglob("*.yaml"):
            if any(part in ignore_patterns for part in workflow_file.relative_to(repo_path).parts):
                continue
            try:
                content = workflow_file.read_text(encoding="utf-8", errors="ignore")
                rel_path = workflow_file.relative_to(repo_path)
                config_files[str(rel_path)] = content[:1000]
            except Exception:
                pass

        # Search for .circleci/config.yml
        circleci_config = repo_path / ".circleci" / "config.yml"
        if circleci_config.exists():
            try:
                content = circleci_config.read_text(encoding="utf-8", errors="ignore")
                rel_path = circleci_config.relative_to(repo_path)
                config_files[str(rel_path)] = content[:1000]
            except Exception:
                pass

        # Search for pyproject.toml (Python modern config)
        for pyproject in repo_path.rglob("pyproject.toml"):
            if any(part in ignore_patterns for part in pyproject.relative_to(repo_path).parts):
                continue
            try:
                content = pyproject.read_text(encoding="utf-8", errors="ignore")
                rel_path = pyproject.relative_to(repo_path)
                config_files[str(rel_path)] = content[:1000]
            except Exception:
                continue

        return config_files

    async def _extract_config_files(self, repo_path: Path, discovery_ignored_dirs: set[str] | None = None) -> dict[str, str]:
        """Extract key configuration files recursively."""
        return await asyncio.to_thread(self._extract_config_files_sync, repo_path, discovery_ignored_dirs)

    def _extract_code_samples_sync(self, repo_path: Path, structure_data: dict[str, Any], discovery_ignored_dirs: set[str] | None = None) -> dict[str, str]:
        """Extract representative code samples (sync I/O)."""
        ignored = discovery_ignored_dirs or set()
        code_samples = {}

        # Get a diverse set of files from file_tree
        if structure_data and "file_tree" in structure_data:
            files_to_sample = []

            # Filter for code files from file_tree
            for node in structure_data["file_tree"]:
                if node.get("type") == "file":
                    file_path = node.get("path", node.get("name", ""))
                    if any(ext in str(file_path) for ext in [".py", ".ts", ".tsx", ".js", ".jsx", ".kt", ".java", ".swift", ".xml"]):
                        # Skip files inside ignored directories
                        if any(part in ignored for part in Path(file_path).parts):
                            continue
                        files_to_sample.append(file_path)

                # Limit initial search
                if len(files_to_sample) >= 50:
                    break

            # Read up to 10 files
            for file_path in files_to_sample[:10]:
                full_path = repo_path / file_path
                if full_path.exists() and full_path.is_file():
                    try:
                        content = full_path.read_text()
                        # Limit to 500 lines
                        lines = content.split('\n')[:500]
                        code_samples[str(file_path)] = '\n'.join(lines)
                    except Exception:
                        pass

        return code_samples

    async def _extract_code_samples(self, repo_path: Path, structure_data: dict[str, Any], discovery_ignored_dirs: set[str] | None = None) -> dict[str, str]:
        """Extract representative code samples."""
        return await asyncio.to_thread(self._extract_code_samples_sync, repo_path, structure_data, discovery_ignored_dirs)

