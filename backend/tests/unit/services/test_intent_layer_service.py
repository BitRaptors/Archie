"""Tests for IntentLayerService consolidation — commit-ready file tree."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from domain.entities.blueprint import BlueprintMeta, StructuredBlueprint
from domain.entities.intent_layer import IntentLayerOutput


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
