"""Tests for IntentLayerService consolidation — commit-ready file tree."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.blueprint import BlueprintMeta, StructuredBlueprint
from domain.entities.intent_layer import (
    IntentLayerOutput,
    GenerationManifest,
    FolderManifestEntry,
)


class TestIntentLayerOutputModel:

    def test_no_codebase_map_field(self):
        """codebase_map was removed — content lives in claude_md_files."""
        output = IntentLayerOutput()
        assert not hasattr(output, "codebase_map") or "codebase_map" not in output.model_fields

    def test_codebase_map_in_claude_md_files(self):
        output = IntentLayerOutput(
            claude_md_files={"CODEBASE_MAP.md": "# Map", "CLAUDE.md": "# Root"},
        )
        assert output.claude_md_files.get("CODEBASE_MAP.md") == "# Map"


class TestPreviewConsolidation:
    """Verify that preview() produces a single commit-ready file tree."""

    @pytest.fixture
    def mock_storage(self):
        storage = AsyncMock()
        storage.exists = AsyncMock(return_value=False)
        storage.read = AsyncMock(return_value=None)
        storage.save = AsyncMock()
        return storage

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.storage_path = "/tmp/test-storage"
        settings.intent_layer_excluded_dirs = ""
        settings.intent_layer_max_depth = 99
        settings.intent_layer_min_files = 2
        settings.intent_layer_max_concurrent = 5
        settings.intent_layer_ai_model = ""
        settings.intent_layer_enable_ai_enrichment = False
        settings.intent_layer_enrichment_model = ""
        settings.intent_layer_generate_codebase_map = True
        return settings

    @pytest.fixture
    def sample_blueprint(self):
        return StructuredBlueprint(
            meta=BlueprintMeta(
                repository="acme/backend-api",
                repository_id="repo-123",
            ),
        )

    @pytest.fixture
    def mock_storage_with_blueprint(self, mock_storage, sample_blueprint):
        """Storage that returns a blueprint and a minimal file tree."""
        import json

        bp_json = json.dumps(sample_blueprint.model_dump()).encode("utf-8")

        async def _exists(path):
            return path == "blueprints/repo-123/blueprint.json"

        async def _read(path):
            if path == "blueprints/repo-123/blueprint.json":
                return bp_json
            return None

        async def _list_files(prefix):
            if prefix == "repos/repo-123":
                return [
                    "repos/repo-123/src/main.py",
                    "repos/repo-123/src/utils.py",
                    "repos/repo-123/README.md",
                ]
            return []

        mock_storage.exists = AsyncMock(side_effect=_exists)
        mock_storage.read = AsyncMock(side_effect=_read)
        mock_storage.list_files = AsyncMock(side_effect=_list_files)
        return mock_storage

    @pytest.mark.asyncio
    async def test_preview_with_blueprint_includes_root_claude_md(
        self, mock_storage_with_blueprint, mock_settings
    ):
        """Root CLAUDE.md should come from blueprint (agent_file_generator)."""
        from application.services.intent_layer_service import IntentLayerService

        service = IntentLayerService(
            storage=mock_storage_with_blueprint,
            settings=mock_settings,
        )
        output = await service.preview(source_repo_id="repo-123")

        assert "CLAUDE.md" in output.claude_md_files
        root_content = output.claude_md_files["CLAUDE.md"]
        # Blueprint-derived root CLAUDE.md has structured sections
        assert "# CLAUDE.md" in root_content

    @pytest.mark.asyncio
    async def test_preview_with_blueprint_includes_agents_md(
        self, mock_storage_with_blueprint, mock_settings
    ):
        """AGENTS.md should be present from blueprint."""
        from application.services.intent_layer_service import IntentLayerService

        service = IntentLayerService(
            storage=mock_storage_with_blueprint,
            settings=mock_settings,
        )
        output = await service.preview(source_repo_id="repo-123")

        assert "AGENTS.md" in output.claude_md_files
        assert "# AGENTS.md" in output.claude_md_files["AGENTS.md"]

    @pytest.mark.asyncio
    async def test_preview_with_blueprint_includes_rule_files(
        self, mock_storage_with_blueprint, mock_settings
    ):
        """Rule files (.claude/rules/, .cursor/rules/) should be present."""
        from application.services.intent_layer_service import IntentLayerService

        service = IntentLayerService(
            storage=mock_storage_with_blueprint,
            settings=mock_settings,
        )
        output = await service.preview(source_repo_id="repo-123")

        claude_rules = [k for k in output.claude_md_files if k.startswith(".claude/rules/")]
        cursor_rules = [k for k in output.claude_md_files if k.startswith(".cursor/rules/")]
        assert len(claude_rules) > 0
        assert len(cursor_rules) > 0

    @pytest.mark.asyncio
    async def test_preview_with_blueprint_includes_codebase_map(
        self, mock_storage_with_blueprint, mock_settings
    ):
        """CODEBASE_MAP.md should be in claude_md_files."""
        from application.services.intent_layer_service import IntentLayerService

        service = IntentLayerService(
            storage=mock_storage_with_blueprint,
            settings=mock_settings,
        )
        output = await service.preview(source_repo_id="repo-123")

        assert "CODEBASE_MAP.md" in output.claude_md_files

    @pytest.mark.asyncio
    async def test_preview_without_blueprint_no_agents_or_rules(
        self, mock_storage, mock_settings, tmp_path
    ):
        """Without a blueprint, only per-folder CLAUDE.md files are generated."""
        from application.services.intent_layer_service import IntentLayerService

        # Create a minimal local repo
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('hello')")
        (src_dir / "utils.py").write_text("def helper(): pass")

        service = IntentLayerService(
            storage=mock_storage,
            settings=mock_settings,
        )
        output = await service.preview(local_path=str(tmp_path))

        # No blueprint → no AGENTS.md, no rule files, no CODEBASE_MAP.md
        assert "AGENTS.md" not in output.claude_md_files
        assert "CODEBASE_MAP.md" not in output.claude_md_files
        assert not any(k.startswith(".claude/rules/") for k in output.claude_md_files)
        assert not any(k.startswith(".cursor/rules/") for k in output.claude_md_files)
        # But per-folder CLAUDE.md is present
        assert "CLAUDE.md" in output.claude_md_files


class TestShouldInclude:
    """Test the _should_include helper on DeliveryService."""

    def test_claude_md(self):
        from application.services.delivery_service import DeliveryService
        assert DeliveryService._should_include("CLAUDE.md", ["claude_md"]) is True
        assert DeliveryService._should_include("CLAUDE.md", ["agents_md"]) is False

    def test_agents_md(self):
        from application.services.delivery_service import DeliveryService
        assert DeliveryService._should_include("AGENTS.md", ["agents_md"]) is True
        assert DeliveryService._should_include("AGENTS.md", ["claude_md"]) is False

    def test_codebase_map(self):
        from application.services.delivery_service import DeliveryService
        assert DeliveryService._should_include("CODEBASE_MAP.md", ["codebase_map"]) is True
        assert DeliveryService._should_include("CODEBASE_MAP.md", ["claude_md"]) is False

    def test_claude_rules(self):
        from application.services.delivery_service import DeliveryService
        assert DeliveryService._should_include(".claude/rules/foo.md", ["claude_rules"]) is True
        assert DeliveryService._should_include(".claude/rules/foo.md", ["cursor_rules"]) is False

    def test_cursor_rules(self):
        from application.services.delivery_service import DeliveryService
        assert DeliveryService._should_include(".cursor/rules/foo.md", ["cursor_rules"]) is True
        assert DeliveryService._should_include(".cursor/rules/foo.md", ["claude_rules"]) is False

    def test_subfolder_claude_md(self):
        from application.services.delivery_service import DeliveryService
        assert DeliveryService._should_include("src/api/CLAUDE.md", ["intent_layer"]) is True
        assert DeliveryService._should_include("src/api/CLAUDE.md", ["claude_md"]) is False


class TestIncrementalEnrichment:
    """Tests for incremental enrichment — manifest-based caching of unchanged folders."""

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.storage_path = "/tmp/test-storage"
        settings.intent_layer_excluded_dirs = ""
        settings.intent_layer_max_depth = 99
        settings.intent_layer_min_files = 2
        settings.intent_layer_max_concurrent = 5
        settings.intent_layer_ai_model = ""
        settings.intent_layer_enable_ai_enrichment = True
        settings.intent_layer_enrichment_model = ""
        settings.intent_layer_generate_codebase_map = True
        settings.default_ai_model = "claude-sonnet-4-20250514"
        return settings

    @pytest.fixture
    def sample_blueprint(self):
        return StructuredBlueprint(
            meta=BlueprintMeta(
                repository="acme/backend-api",
                repository_id="repo-123",
            ),
        )

    def _make_storage(self, blueprint, manifest=None, cached_files=None):
        """Build a mock storage with blueprint, optional manifest, and optional cached intent layer files."""
        storage = AsyncMock()
        bp_json = json.dumps(blueprint.model_dump()).encode("utf-8")
        manifest_json = json.dumps(manifest.model_dump(mode="json")).encode("utf-8") if manifest else None

        async def _exists(path):
            if path == "blueprints/repo-123/blueprint.json":
                return True
            if path == "blueprints/repo-123/intent_layer_manifest.json" and manifest is not None:
                return True
            if cached_files and path.startswith("blueprints/repo-123/intent_layer/"):
                rel = path[len("blueprints/repo-123/intent_layer/"):]
                return rel in cached_files
            return False

        async def _read(path):
            if path == "blueprints/repo-123/blueprint.json":
                return bp_json
            if path == "blueprints/repo-123/intent_layer_manifest.json" and manifest_json:
                return manifest_json
            if cached_files and path.startswith("blueprints/repo-123/intent_layer/"):
                rel = path[len("blueprints/repo-123/intent_layer/"):]
                if rel in cached_files:
                    return cached_files[rel].encode("utf-8")
            return None

        async def _list_files(prefix):
            if prefix == "repos/repo-123":
                return [
                    "repos/repo-123/src/main.py",
                    "repos/repo-123/src/utils.py",
                    "repos/repo-123/README.md",
                ]
            return []

        storage.exists = AsyncMock(side_effect=_exists)
        storage.read = AsyncMock(side_effect=_read)
        storage.save = AsyncMock()
        storage.list_files = AsyncMock(side_effect=_list_files)
        return storage

    @pytest.mark.asyncio
    async def test_incremental_false_runs_full_enrichment(self, mock_settings, sample_blueprint):
        """incremental=False should enrich all folders regardless of manifest."""
        storage = self._make_storage(sample_blueprint)

        from application.services.intent_layer_service import IntentLayerService
        service = IntentLayerService(storage=storage, settings=mock_settings)
        output = await service.preview(source_repo_id="repo-123", incremental=False)

        # incremental=False should never skip any folders
        assert output.folder_count > 0
        assert output.skipped_folder_count == 0

    @pytest.mark.asyncio
    async def test_incremental_true_no_manifest_enriches_all(self, mock_settings, sample_blueprint):
        """incremental=True with no existing manifest should enrich all, skipped_folder_count == 0."""
        storage = self._make_storage(sample_blueprint, manifest=None)

        from application.services.intent_layer_service import IntentLayerService
        service = IntentLayerService(storage=storage, settings=mock_settings)
        output = await service.preview(source_repo_id="repo-123", incremental=True)

        assert output.folder_count > 0
        assert output.skipped_folder_count == 0

    @pytest.mark.asyncio
    async def test_incremental_true_blueprint_hash_changed_enriches_all(self, mock_settings, sample_blueprint):
        """incremental=True with different blueprint hash should re-enrich everything."""
        # Create a manifest with a different blueprint hash
        old_manifest = GenerationManifest(
            blueprint_hash="old-hash-does-not-match",
            entries=[
                FolderManifestEntry(path="src/CLAUDE.md", content_hash="abc123"),
            ],
        )
        storage = self._make_storage(
            sample_blueprint,
            manifest=old_manifest,
            cached_files={"src/CLAUDE.md": "# cached content"},
        )

        from application.services.intent_layer_service import IntentLayerService
        service = IntentLayerService(storage=storage, settings=mock_settings)
        output = await service.preview(source_repo_id="repo-123", incremental=True)

        # Blueprint hash mismatch → ManifestManager.diff returns everything as changed
        assert output.skipped_folder_count == 0

    @pytest.mark.asyncio
    async def test_incremental_true_all_unchanged_uses_cache(self, mock_settings, sample_blueprint):
        """incremental=True with all folders unchanged should use cache, total_ai_calls == 0."""
        from application.services.intent_layer_service import IntentLayerService, FolderHierarchyBuilder
        from application.services.blueprint_folder_mapper import BlueprintFolderMapper, compute_blueprint_hash
        from application.services.intent_layer_renderer import IntentLayerRenderer
        from application.services.intent_layer_manifest import _content_hash

        # Build the same deterministic content that the manifest saving code produces
        bp_hash = compute_blueprint_hash(sample_blueprint)

        # Simulate the exact deterministic renders the code uses for manifest
        # by using the same mapper/renderer on the file tree
        storage_setup = self._make_storage(sample_blueprint)
        service_setup = IntentLayerService(storage=storage_setup, settings=mock_settings)
        file_tree = await service_setup._load_file_tree("repo-123")
        builder = FolderHierarchyBuilder()
        nodes = builder.build_from_file_tree(file_tree)
        significant = builder.filter_significant(nodes)
        folder_paths = list(significant.keys())

        mapper = BlueprintFolderMapper()
        renderer = IntentLayerRenderer()
        all_fb = mapper.map_all(sample_blueprint, folder_paths)

        det_files: dict[str, str] = {}
        for fp, fb in all_fb.items():
            node = nodes.get(fp)
            if not node:
                continue
            mp = f"{fp}/CLAUDE.md" if fp else "CLAUDE.md"
            if node.is_passthrough:
                det_files[mp] = renderer.render_passthrough(node, fb, "acme/backend-api")
            elif fb.has_blueprint_coverage:
                det_files[mp] = renderer.render_from_blueprint(node, fb, "acme/backend-api")
            else:
                det_files[mp] = renderer.render_minimal(node, fb, "acme/backend-api")

        entries = [
            FolderManifestEntry(path=path, content_hash=_content_hash(content))
            for path, content in det_files.items()
        ]
        manifest = GenerationManifest(blueprint_hash=bp_hash, entries=entries)

        # Build cached files — these are the final AI-enriched output from storage
        # For this test, just use the deterministic files as cached output
        cached_files = dict(det_files)

        storage = self._make_storage(sample_blueprint, manifest=manifest, cached_files=cached_files)
        service = IntentLayerService(storage=storage, settings=mock_settings)
        output = await service.preview(source_repo_id="repo-123", incremental=True)

        assert output.folder_count > 0
        assert output.total_ai_calls == 0
        assert output.skipped_folder_count > 0
        # All CLAUDE.md files should still be present in output
        for path in det_files:
            assert path in output.claude_md_files

    @pytest.mark.asyncio
    async def test_incremental_true_storage_read_fails_falls_back(self, mock_settings, sample_blueprint):
        """When cached file read fails, folder should fall back to re-enrichment."""
        from application.services.intent_layer_service import IntentLayerService
        from application.services.blueprint_folder_mapper import compute_blueprint_hash
        from application.services.intent_layer_manifest import _content_hash

        # Run deterministic preview to build manifest
        det_settings = MagicMock()
        for attr in dir(mock_settings):
            if not attr.startswith('_'):
                setattr(det_settings, attr, getattr(mock_settings, attr))
        det_settings.intent_layer_enable_ai_enrichment = False
        storage_first = self._make_storage(sample_blueprint)
        service_first = IntentLayerService(storage=storage_first, settings=det_settings)
        first_output = await service_first.preview(source_repo_id="repo-123", incremental=False)

        bp_hash = compute_blueprint_hash(sample_blueprint)
        det_files = {
            path: content for path, content in first_output.claude_md_files.items()
            if path.endswith("CLAUDE.md")
        }
        entries = [
            FolderManifestEntry(path=path, content_hash=_content_hash(content))
            for path, content in det_files.items()
        ]
        manifest = GenerationManifest(blueprint_hash=bp_hash, entries=entries)

        # Storage with manifest but NO cached intent layer files
        storage = self._make_storage(sample_blueprint, manifest=manifest, cached_files=None)

        # Override exists to return False for cached files
        original_exists = storage.exists.side_effect

        async def _exists_no_cache(path):
            if path.startswith("blueprints/repo-123/intent_layer/"):
                return False
            return await original_exists(path)

        storage.exists = AsyncMock(side_effect=_exists_no_cache)

        service = IntentLayerService(storage=storage, settings=mock_settings)
        output = await service.preview(source_repo_id="repo-123", incremental=True)

        # All folders should be re-enriched (none skipped because cache is missing)
        assert output.skipped_folder_count == 0
        assert output.folder_count > 0
