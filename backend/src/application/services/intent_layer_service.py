"""Intent Layer service — orchestrates per-folder CLAUDE.md generation."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from domain.entities.blueprint import StructuredBlueprint
from domain.entities.intent_layer import (
    FolderNode,
    FolderBlueprint,
    FolderEnrichment,
    IntentLayerConfig,
    IntentLayerOutput,
)
from domain.entities.analysis_settings import SOURCE_CODE_EXTENSIONS
from infrastructure.persistence.analysis_settings_repository import IgnoredDirsRepository

logger = logging.getLogger(__name__)

# Files that exist for namespace/module plumbing only — not real source code
_TRIVIAL_MARKERS = {"__init__.py", "__init__.pyi", "__main__.py", "py.typed", "package-info.java", "mod.rs"}


class FolderHierarchyBuilder:
    """Builds a hierarchy of FolderNodes from a file tree."""

    def __init__(self, config: IntentLayerConfig | None = None, ignored_dirs: set[str] | None = None):
        self._config = config or IntentLayerConfig()
        # Combine configured exclusions with DB-loaded ignored dirs
        self._excluded = self._config.excluded_dirs | (ignored_dirs or set())

    def build_from_path(self, repo_path: Path) -> dict[str, FolderNode]:
        """Walk a local directory and build FolderNode hierarchy."""
        nodes: dict[str, FolderNode] = {}
        repo_path = repo_path.resolve()

        for root, dirs, files in os.walk(repo_path):
            # Filter in-place
            dirs[:] = sorted([
                d for d in dirs
                if d not in self._excluded and not d.startswith('.')
            ])

            rel = os.path.relpath(root, repo_path)
            if rel == '.':
                rel = ''

            depth = 0 if rel == '' else rel.count(os.sep) + 1
            name = os.path.basename(root) if rel else os.path.basename(repo_path)
            parent = os.path.dirname(rel) if rel else ''

            # Collect direct files (skip hidden)
            direct_files = sorted([f for f in files if not f.startswith('.')])
            extensions = sorted(set(
                Path(f).suffix.lstrip('.') for f in direct_files if Path(f).suffix
            ))

            node = FolderNode(
                path=rel,
                name=name,
                depth=depth,
                parent_path=parent,
                files=direct_files,
                file_count=len(direct_files),  # Will be updated below for recursive count
                children=[],
                extensions=extensions,
            )
            nodes[rel] = node

        # Wire children and compute recursive file counts
        for path, node in nodes.items():
            if path and node.parent_path in nodes:
                parent_node = nodes[node.parent_path]
                if path not in parent_node.children:
                    parent_node.children.append(path)

        # Compute recursive file counts (bottom-up)
        for path in sorted(nodes.keys(), key=lambda p: p.count(os.sep), reverse=True):
            node = nodes[path]
            recursive_count = len(node.files)
            for child_path in node.children:
                if child_path in nodes:
                    recursive_count += nodes[child_path].file_count
            node.file_count = recursive_count

        # Mark pass-through namespace folders
        for path, node in nodes.items():
            if node.depth == 0:
                continue
            source_files = [f for f in node.files if f not in _TRIVIAL_MARKERS]
            node.is_passthrough = len(source_files) == 0 and len(node.children) == 1

        return nodes

    def build_from_file_tree(self, file_tree: list[dict]) -> dict[str, FolderNode]:
        """Parse structure_analyzer output format: [{name, path, type, size, extension}].

        Builds folder nodes by extracting directory structure from file paths.
        """
        # Collect all directories and their files
        dir_files: dict[str, list[str]] = {}  # dir_path -> [filenames]
        dir_extensions: dict[str, set[str]] = {}

        for entry in file_tree:
            if entry.get("type") != "file":
                continue
            file_path = entry["path"]
            dir_path = os.path.dirname(file_path)

            # Normalize
            if dir_path == '.':
                dir_path = ''

            if dir_path not in dir_files:
                dir_files[dir_path] = []
                dir_extensions[dir_path] = set()

            dir_files[dir_path].append(entry["name"])
            ext = entry.get("extension", "")
            if ext:
                dir_extensions[dir_path].add(ext)

            # Ensure all parent directories exist
            parts = dir_path.split(os.sep) if dir_path else []
            for i in range(len(parts)):
                parent = os.sep.join(parts[:i + 1])
                if parent not in dir_files:
                    dir_files[parent] = []
                    dir_extensions[parent] = set()

        # Always include root
        if '' not in dir_files:
            dir_files[''] = []
            dir_extensions[''] = set()

        # Filter excluded dirs
        filtered_dirs = {}
        for dir_path in dir_files:
            parts = dir_path.split(os.sep) if dir_path else ['']
            if any(p in self._excluded or p.startswith('.') for p in parts if p):
                continue
            filtered_dirs[dir_path] = dir_files[dir_path]

        # Build nodes
        nodes: dict[str, FolderNode] = {}
        for dir_path in sorted(filtered_dirs.keys()):
            depth = 0 if dir_path == '' else dir_path.count(os.sep) + 1
            name = os.path.basename(dir_path) if dir_path else 'root'
            parent = os.path.dirname(dir_path) if dir_path else ''

            files = sorted(filtered_dirs[dir_path])
            exts = sorted(dir_extensions.get(dir_path, set()))

            node = FolderNode(
                path=dir_path,
                name=name,
                depth=depth,
                parent_path=parent if dir_path else '',
                files=files,
                file_count=len(files),
                children=[],
                extensions=exts,
            )
            nodes[dir_path] = node

        # Wire children
        for path, node in nodes.items():
            if path and node.parent_path in nodes:
                nodes[node.parent_path].children.append(path)

        # Recursive file counts (bottom-up)
        for path in sorted(nodes.keys(), key=lambda p: p.count(os.sep) if p else -1, reverse=True):
            node = nodes[path]
            recursive_count = len(node.files)
            for child_path in node.children:
                if child_path in nodes:
                    recursive_count += nodes[child_path].file_count
            node.file_count = recursive_count

        # Mark pass-through namespace folders
        for path, node in nodes.items():
            if node.depth == 0:
                continue
            source_files = [f for f in node.files if f not in _TRIVIAL_MARKERS]
            node.is_passthrough = len(source_files) == 0 and len(node.children) == 1

        return nodes

    @staticmethod
    def _has_source_code(node: FolderNode) -> bool:
        """Check if a folder contains at least one source code file (by extension)."""
        return any(
            Path(f).suffix in SOURCE_CODE_EXTENSIONS
            for f in node.files
        )

    @staticmethod
    def _subtree_has_source_code(node: FolderNode, nodes: dict[str, FolderNode]) -> bool:
        """Check if a folder or any descendant contains source code files.

        Handles resource trees like Assets.xcassets/ where the parent has
        children but no descendant contains actual code.
        """
        stack = [node]
        while stack:
            current = stack.pop()
            if any(Path(f).suffix in SOURCE_CODE_EXTENSIONS for f in current.files):
                return True
            for child_path in current.children:
                child = nodes.get(child_path)
                if child:
                    stack.append(child)
        return False

    def filter_significant(self, nodes: dict[str, FolderNode]) -> dict[str, FolderNode]:
        """Remove folders below min_files threshold, beyond max_depth, or resource-only.

        Always keeps root (depth 0). Skips folders whose entire subtree contains
        no source code files (e.g. Assets.xcassets/, res/drawable/, assets/fonts/).
        """
        return {
            path: node for path, node in nodes.items()
            if node.depth == 0  # Always keep root
            or (
                node.file_count >= self._config.min_files
                and node.depth <= self._config.max_depth
                and self._subtree_has_source_code(node, nodes)
            )
        }

    def group_by_depth(self, nodes: dict[str, FolderNode]) -> dict[int, list[FolderNode]]:
        """Group nodes by depth level for BFS processing."""
        groups: dict[int, list[FolderNode]] = {}
        for node in nodes.values():
            if node.depth not in groups:
                groups[node.depth] = []
            groups[node.depth].append(node)
        # Sort within each depth for deterministic ordering
        for depth in groups:
            groups[depth].sort(key=lambda n: n.path)
        return groups

    @staticmethod
    def batch_siblings(nodes_at_depth: list[FolderNode], batch_size: int = 4) -> list[list[FolderNode]]:
        """Group same-parent folders into batches for concurrent AI calls."""
        # Group by parent
        by_parent: dict[str, list[FolderNode]] = {}
        for node in nodes_at_depth:
            parent = node.parent_path
            if parent not in by_parent:
                by_parent[parent] = []
            by_parent[parent].append(node)

        # Batch within each parent group
        batches: list[list[FolderNode]] = []
        for parent_path in sorted(by_parent.keys()):
            siblings = by_parent[parent_path]
            for i in range(0, len(siblings), batch_size):
                batches.append(siblings[i:i + batch_size])

        return batches


class IntentLayerService:
    """Orchestrates the full intent layer generation pipeline.

    Default path: deterministic blueprint-driven rendering (no AI calls).
    Optional AI enrichment for folders with zero blueprint coverage.
    """

    def __init__(self, storage, settings, db_client=None):
        self._storage = storage
        self._settings = settings
        self._db_client = db_client

    async def preview(
        self,
        source_repo_id: str | None = None,
        local_path: str | None = None,
        config: IntentLayerConfig | None = None,
        progress_callback=None,
    ) -> IntentLayerOutput:
        """Generate intent layer output without writing files.

        Blueprint-first: deterministic rendering from StructuredBlueprint.
        Falls back to AI enrichment only if config.enable_ai_enrichment is True.
        """
        from application.services.blueprint_folder_mapper import BlueprintFolderMapper, compute_blueprint_hash
        from application.services.intent_layer_renderer import IntentLayerRenderer
        from application.services.codebase_map_renderer import CodebaseMapRenderer
        from application.services.intent_layer_manifest import ManifestManager
        from domain.exceptions.domain_exceptions import ValidationError

        if not source_repo_id and not local_path:
            raise ValidationError("Either source_repo_id or local_path is required")

        config = config or self._build_config()
        start_time = time.time()

        # Load ignored dirs from DB
        ignored_dirs = await self._load_ignored_dirs()
        builder = FolderHierarchyBuilder(config, ignored_dirs=ignored_dirs)

        # Build hierarchy
        if local_path:
            from application.services.local_repo_handler import LocalRepoHandler
            handler = LocalRepoHandler(Path(local_path), ignored_dirs=ignored_dirs)
            file_tree = await asyncio.to_thread(handler.build_file_tree)
            nodes = builder.build_from_file_tree(file_tree)
            repo_name = Path(local_path).name
        else:
            file_tree = await self._load_file_tree(source_repo_id)
            nodes = builder.build_from_file_tree(file_tree)
            repo_name = source_repo_id

        # Filter significant folders
        significant = builder.filter_significant(nodes)
        folder_paths = list(significant.keys())

        # Load full blueprint
        blueprint = None
        if source_repo_id:
            blueprint = await self._load_blueprint(source_repo_id)

        # Deterministic path: map blueprint onto folders
        mapper = BlueprintFolderMapper()
        renderer = IntentLayerRenderer()
        claude_md_files: dict[str, str] = {}
        total_ai_calls = 0

        if blueprint:
            folder_blueprints = mapper.map_all(blueprint, folder_paths)

            if config.enable_ai_enrichment:
                # Hybrid path: AI enrichment for ALL significant folders
                from application.services.hybrid_enrichment_engine import HybridEnrichmentEngine

                logger.info(
                    f"Intent layer: hybrid enrichment enabled for {len(significant)} folders "
                    f"(blueprint covers {sum(1 for fb in folder_blueprints.values() if fb.has_blueprint_coverage)})"
                )
                engine = HybridEnrichmentEngine(self._settings, config, progress_callback=progress_callback)
                file_reader = self._make_storage_reader(source_repo_id) if source_repo_id else self._make_storage_reader(repo_name)

                # Read previous CLAUDE.md content for AI context
                previous_content: dict[str, str] = {}
                for folder_path in significant:
                    md_rel = f"{folder_path}/CLAUDE.md" if folder_path else "CLAUDE.md"
                    raw = file_reader(md_rel)
                    if raw:
                        previous_content[folder_path] = raw

                enrichments = await engine.enrich_all(significant, folder_blueprints, file_reader, previous_content)
                total_ai_calls = engine.total_calls

                for folder_path, fb in folder_blueprints.items():
                    node = significant.get(folder_path)
                    if not node:
                        continue
                    md_path = f"{folder_path}/CLAUDE.md" if folder_path else "CLAUDE.md"
                    if node.is_passthrough:
                        claude_md_files[md_path] = renderer.render_passthrough(node, fb, repo_name)
                        continue
                    enrichment = enrichments.get(folder_path, FolderEnrichment(path=folder_path))
                    claude_md_files[md_path] = renderer.render_hybrid(node, fb, enrichment, repo_name)
            else:
                # Deterministic-only path (no AI calls)
                for folder_path, fb in folder_blueprints.items():
                    node = significant.get(folder_path)
                    if not node:
                        continue
                    md_path = f"{folder_path}/CLAUDE.md" if folder_path else "CLAUDE.md"
                    if node.is_passthrough:
                        claude_md_files[md_path] = renderer.render_passthrough(node, fb, repo_name)
                    elif fb.has_blueprint_coverage:
                        claude_md_files[md_path] = renderer.render_from_blueprint(node, fb, repo_name)
                    else:
                        claude_md_files[md_path] = renderer.render_minimal(node, fb, repo_name)
        else:
            # No blueprint available — render minimal for all
            for folder_path in folder_paths:
                node = significant.get(folder_path)
                if not node:
                    continue
                from domain.entities.intent_layer import FolderBlueprint
                fb = FolderBlueprint(path=folder_path)
                md_path = f"{folder_path}/CLAUDE.md" if folder_path else "CLAUDE.md"
                claude_md_files[md_path] = renderer.render_minimal(node, fb, repo_name)

        # Generate codebase map
        codebase_map = ""
        if config.generate_codebase_map and blueprint:
            codebase_map = CodebaseMapRenderer().render(blueprint)

        # Incremental update tracking (build manifest without copying the full dict)
        if source_repo_id and blueprint:
            try:
                manifest_mgr = ManifestManager(self._storage)
                bp_hash = compute_blueprint_hash(blueprint)
                # Pass claude_md_files directly; add codebase_map entry in-place temporarily
                if codebase_map:
                    claude_md_files["CODEBASE_MAP.md"] = codebase_map
                manifest = manifest_mgr.build_manifest(bp_hash, claude_md_files)
                if codebase_map:
                    del claude_md_files["CODEBASE_MAP.md"]
                await manifest_mgr.save(source_repo_id, manifest)
            except Exception as e:
                logger.warning(f"Failed to save manifest: {e}")

        elapsed = time.time() - start_time

        return IntentLayerOutput(
            claude_md_files=claude_md_files,
            codebase_map=codebase_map,
            folder_count=len(significant),
            total_ai_calls=total_ai_calls,
            generation_time_seconds=round(elapsed, 2),
        )

    async def apply_local(
        self,
        local_path: str,
        config: IntentLayerConfig | None = None,
    ) -> IntentLayerOutput:
        """Generate and write intent layer files to a local repo."""
        from application.services.local_repo_handler import LocalRepoHandler

        output = await self.preview(local_path=local_path, config=config)
        ignored_dirs = await self._load_ignored_dirs()
        handler = LocalRepoHandler(Path(local_path), ignored_dirs=ignored_dirs)
        repo_name = Path(local_path).name

        # Write CLAUDE.md files with merge
        for rel_path, content in output.claude_md_files.items():
            await asyncio.to_thread(handler.write_merged_markdown, rel_path, content, repo_name)

        return output

    # ── Internal helpers ──

    def _build_config(self) -> IntentLayerConfig:
        """Build IntentLayerConfig from application settings."""
        excluded = set()
        raw = getattr(self._settings, 'intent_layer_excluded_dirs', '')
        if raw:
            excluded = {d.strip() for d in raw.split(',') if d.strip()}

        return IntentLayerConfig(
            max_depth=getattr(self._settings, 'intent_layer_max_depth', 99),
            min_files=getattr(self._settings, 'intent_layer_min_files', 2),
            max_concurrent=getattr(self._settings, 'intent_layer_max_concurrent', 5),
            excluded_dirs=excluded,
            ai_model=getattr(self._settings, 'intent_layer_ai_model', ''),
            enable_ai_enrichment=getattr(self._settings, 'intent_layer_enable_ai_enrichment', True),
            enrichment_model=getattr(self._settings, 'intent_layer_enrichment_model', ''),
            generate_codebase_map=getattr(self._settings, 'intent_layer_generate_codebase_map', True),
        )

    async def _load_ignored_dirs(self) -> set[str]:
        """Load ignored directories from the database."""
        if not self._db_client:
            logger.warning("No DB client available — ignored dirs will be empty")
            return set()
        try:
            repo = IgnoredDirsRepository(db=self._db_client)
            rows = await repo.get_all()
            if rows:
                return {d.directory_name for d in rows}
        except Exception as e:
            logger.warning(f"Failed to load ignored dirs from DB: {e}")
        return set()

    async def _load_file_tree(self, repo_id: str) -> list[dict]:
        """Load file tree from stored repo files."""
        repo_dir = f"repos/{repo_id}"
        # Try to list files from storage
        try:
            if hasattr(self._storage, 'list_files'):
                files = await self._storage.list_files(repo_dir)
                return [
                    {"name": os.path.basename(f), "path": f, "type": "file", "size": 0, "extension": Path(f).suffix.lstrip('.')}
                    for f in files
                ]
        except Exception:
            pass
        # Fallback: try local storage path
        local_path = Path(self._settings.storage_path) / repo_dir
        if local_path.exists():
            from application.services.local_repo_handler import LocalRepoHandler
            ignored_dirs = await self._load_ignored_dirs()
            handler = LocalRepoHandler(local_path, ignored_dirs=ignored_dirs)
            return await asyncio.to_thread(handler.build_file_tree)
        return []

    async def _load_blueprint(self, repo_id: str) -> StructuredBlueprint | None:
        """Load a full StructuredBlueprint from storage."""
        json_path = f"blueprints/{repo_id}/blueprint.json"
        try:
            if await self._storage.exists(json_path):
                content = await self._storage.read(json_path)
                text = content.decode("utf-8") if isinstance(content, bytes) else content
                data = json.loads(text)
                return StructuredBlueprint.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load blueprint: {e}")
        return None

    def _make_storage_reader(self, repo_id: str):
        """Create a file reader function for stored repos."""
        base_path = Path(self._settings.storage_path) / f"repos/{repo_id}"

        def reader(rel_path: str) -> str | None:
            target = base_path / rel_path
            if not target.is_file():
                return None
            try:
                return target.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                return None

        return reader

