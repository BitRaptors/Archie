"""Analysis service orchestrator."""
from pathlib import Path
from typing import Any
from domain.entities.analysis import Analysis
from domain.entities.repository import Repository
from domain.entities.analysis_event import AnalysisEvent
from domain.interfaces.repositories import IRepository, IAnalysisEventRepository
from domain.exceptions.domain_exceptions import NotFoundError
from infrastructure.analysis.structure_analyzer import StructureAnalyzer
from infrastructure.storage.storage_interface import IStorage
from application.services.phased_blueprint_generator import PhasedBlueprintGenerator


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
    ):
        """Initialize analysis service."""
        self._analysis_repo = analysis_repo
        self._repository_repo = repository_repo
        self._event_repo = event_repo
        self._structure_analyzer = structure_analyzer
        self._persistent_storage = persistent_storage
        self._phased_blueprint_generator = phased_blueprint_generator

    async def _log_event(self, analysis_id: str, event_type: str, message: str, details: dict | None = None) -> None:
        """Log an analysis event."""
        event = AnalysisEvent.create(analysis_id, event_type, message, details)
        await self._event_repo.add(event)

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
            # Phase 1: Structure scan (data extraction only)
            await self._log_event(analysis_id, "PHASE_START", "Phase 1: Scanning file structure")
            analysis.update_progress(10)
            await self._analysis_repo.update(analysis)
            structure_data = await self._structure_analyzer.analyze(repo_path)
            await self._log_event(analysis_id, "PHASE_END", "Phase 1 complete: File structure indexed")

            # Phase 2: Prepare data for phased analysis
            await self._log_event(analysis_id, "PHASE_START", "Phase 2: Preparing repository data")
            analysis.update_progress(20)
            await self._analysis_repo.update(analysis)
            
            # Extract file tree
            file_tree = self._format_file_tree(structure_data)
            
            # Extract dependencies
            dependencies = await self._extract_dependencies(repo_path)
            
            # Extract config files
            config_files = await self._extract_config_files(repo_path)
            
            # Extract code samples
            code_samples = await self._extract_code_samples(repo_path, structure_data)
            
            await self._log_event(analysis_id, "PHASE_END", "Phase 2 complete: Repository data prepared")

            # Phase 3-8: Phased blueprint generation (AI-driven)
            await self._log_event(analysis_id, "PHASE_START", "Phase 3: Running phased AI analysis")
            analysis.update_progress(30)
            await self._analysis_repo.update(analysis)
            
            # Get repository name
            repo = await self._repository_repo.get_by_id(analysis.repository_id)
            repo_name = repo.full_name if repo else analysis.repository_id
            
            # Generate comprehensive blueprint through phased AI analysis with RAG
            # The generator will:
            # 1. Index the repository (generate embeddings for all code)
            # 2. For each phase, retrieve semantically relevant code
            # 3. Analyze with full codebase visibility
            blueprint = await self._phased_blueprint_generator.generate(
                repo_path=repo_path,
                repository_name=repo_name,
                repository_id=analysis.repository_id,  # Enable RAG retrieval
                file_tree=file_tree,
                dependencies=dependencies,
                config_files=config_files,
                code_samples=code_samples,
            )
            
            # Update progress as phases complete
            await self._log_event(analysis_id, "INFO", "Discovery phase complete")
            analysis.update_progress(40)
            await self._analysis_repo.update(analysis)
            
            await self._log_event(analysis_id, "INFO", "Layer identification complete")
            analysis.update_progress(50)
            await self._analysis_repo.update(analysis)
            
            await self._log_event(analysis_id, "INFO", "Pattern extraction complete")
            analysis.update_progress(60)
            await self._analysis_repo.update(analysis)
            
            await self._log_event(analysis_id, "INFO", "Communication analysis complete")
            analysis.update_progress(70)
            await self._analysis_repo.update(analysis)
            
            await self._log_event(analysis_id, "INFO", "Technology inventory complete")
            analysis.update_progress(80)
            await self._analysis_repo.update(analysis)
            
            await self._log_event(analysis_id, "INFO", "Final synthesis complete")
            analysis.update_progress(90)
            await self._analysis_repo.update(analysis)
            
            await self._log_event(analysis_id, "PHASE_END", "Phase 3 complete: Comprehensive blueprint generated")

            # Phase 4: Save blueprint
            await self._log_event(analysis_id, "PHASE_START", "Phase 4: Saving blueprint")
            analysis.update_progress(95)
            await self._analysis_repo.update(analysis)
            
            blueprint_path = f"blueprints/{analysis.repository_id}/blueprint.md"
            await self._persistent_storage.save(blueprint_path, blueprint)
            await self._log_event(analysis_id, "INFO", "Blueprint saved")
            
            await self._log_event(analysis_id, "PHASE_END", "Phase 4 complete: Blueprint saved")

            # Complete analysis
            await self._log_event(analysis_id, "INFO", "Analysis completed successfully")
            analysis.update_progress(100)
            analysis.complete()
            await self._analysis_repo.update(analysis)

        except Exception as e:
            await self._log_event(analysis_id, "ERROR", f"Analysis failed: {str(e)}")
            analysis.fail(str(e))
            await self._analysis_repo.update(analysis)
            raise

    def _format_file_tree(self, structure_data: dict[str, Any]) -> str:
        """Format structure data as a compressed file tree."""
        if not structure_data or "directories" not in structure_data:
            return "No structure data available"
        
        lines = []
        for directory in structure_data["directories"][:50]:  # Limit to first 50 dirs
            lines.append(f"📁 {directory}")
        
        if "files" in structure_data:
            for file_info in structure_data["files"][:100]:  # Limit to first 100 files
                if isinstance(file_info, dict):
                    lines.append(f"📄 {file_info.get('path', 'unknown')}")
                else:
                    lines.append(f"📄 {file_info}")
        
        return "\n".join(lines)

    async def _extract_dependencies(self, repo_path: Path) -> str:
        """Extract dependencies from package files."""
        dependencies = []
        
        # Python dependencies
        requirements_file = repo_path / "requirements.txt"
        if requirements_file.exists():
            try:
                content = requirements_file.read_text()
                dependencies.append(f"**requirements.txt:**\n```\n{content[:1000]}\n```")
            except Exception:
                pass
        
        # Node dependencies
        package_json = repo_path / "package.json"
        if package_json.exists():
            try:
                content = package_json.read_text()
                dependencies.append(f"**package.json:**\n```json\n{content[:1000]}\n```")
            except Exception:
                pass
        
        return "\n\n".join(dependencies) if dependencies else "No dependency files found"

    async def _extract_config_files(self, repo_path: Path) -> dict[str, str]:
        """Extract key configuration files."""
        config_files = {}
        
        config_patterns = [
            ".env.example",
            "config.py",
            "settings.py",
            "docker-compose.yml",
            "Dockerfile",
        ]
        
        for pattern in config_patterns:
            config_file = repo_path / pattern
            if config_file.exists():
                try:
                    content = config_file.read_text()
                    config_files[pattern] = content[:500]  # Limit content
                except Exception:
                    pass
        
        return config_files

    async def _extract_code_samples(self, repo_path: Path, structure_data: dict[str, Any]) -> dict[str, str]:
        """Extract representative code samples."""
        code_samples = {}
        
        # Get a diverse set of files
        if "files" in structure_data:
            files_to_sample = []
            
            # Prioritize important file types
            for file_info in structure_data["files"][:50]:
                file_path = file_info.get("path") if isinstance(file_info, dict) else file_info
                if any(ext in str(file_path) for ext in [".py", ".ts", ".tsx", ".js", ".jsx"]):
                    files_to_sample.append(file_path)
            
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
