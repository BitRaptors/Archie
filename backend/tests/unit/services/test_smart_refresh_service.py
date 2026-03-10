"""Tests for SmartRefreshService."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.blueprint import (
    BlueprintMeta,
    Component,
    Components,
    ArchitectureRules,
    FilePlacementRule,
    NamingConvention,
    QuickReference,
    StructuredBlueprint,
)
from application.services.smart_refresh_service import (
    SmartRefreshService,
    SmartRefreshResult,
    _is_source_file,
    _read_local_file,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_blueprint() -> StructuredBlueprint:
    return StructuredBlueprint(
        meta=BlueprintMeta(
            repository="acme/backend-api",
            repository_id="repo-123",
            architecture_style="layered",
        ),
        components=Components(
            structure_type="layered",
            components=[
                Component(
                    name="API Layer",
                    location="src/api",
                    responsibility="HTTP request handling",
                    depends_on=["Service Layer"],
                    exposes_to=["External clients"],
                ),
                Component(
                    name="Service Layer",
                    location="src/services",
                    responsibility="Business logic orchestration",
                    depends_on=["Domain Layer"],
                    exposes_to=["API Layer"],
                ),
            ],
        ),
        architecture_rules=ArchitectureRules(
            file_placement_rules=[
                FilePlacementRule(
                    component_type="route",
                    naming_pattern="*_routes.py",
                    location="src/api",
                    example="src/api/user_routes.py",
                    description="API route handlers",
                ),
                FilePlacementRule(
                    component_type="service",
                    naming_pattern="*_service.py",
                    location="src/services",
                    example="src/services/user_service.py",
                    description="Business logic services",
                ),
            ],
            naming_conventions=[
                NamingConvention(scope="files", pattern="snake_case", description="All files use snake_case"),
            ],
        ),
        quick_reference=QuickReference(
            where_to_put_code={"routes": "src/api", "services": "src/services"},
        ),
    )


@pytest.fixture
def mock_storage(sample_blueprint):
    bp_json = json.dumps(sample_blueprint.model_dump()).encode("utf-8")

    async def _exists(path):
        if path == "blueprints/repo-123/blueprint.json":
            return True
        return False

    async def _read(path):
        if path == "blueprints/repo-123/blueprint.json":
            return bp_json
        raise FileNotFoundError(path)

    storage = AsyncMock()
    storage.exists = AsyncMock(side_effect=_exists)
    storage.read = AsyncMock(side_effect=_read)
    storage.save = AsyncMock()
    return storage


@pytest.fixture
def mock_settings():
    mock = MagicMock()
    mock.anthropic_api_key = "test-key"
    mock.storage_path = "/tmp/storage"
    return mock


@pytest.fixture
def mock_intent_layer_service():
    svc = AsyncMock()
    preview_result = MagicMock()
    preview_result.claude_md_files = {
        "src/api/CLAUDE.md": "# API Layer\nUpdated content",
    }
    svc.preview = AsyncMock(return_value=preview_result)
    return svc


@pytest.fixture
def service(mock_storage, mock_settings):
    return SmartRefreshService(storage=mock_storage, settings=mock_settings)


@pytest.fixture
def service_with_intent(mock_storage, mock_settings, mock_intent_layer_service):
    return SmartRefreshService(
        storage=mock_storage,
        settings=mock_settings,
        intent_layer_service=mock_intent_layer_service,
    )


def _make_ai_response(folders_data: list[dict]) -> MagicMock:
    """Build a mock AI response returning the given folder results."""
    text = json.dumps({"folders": folders_data})
    return MagicMock(content=[MagicMock(text=text)])


# ── Pipeline Tests ────────────────────────────────────────────────────────────


class TestSmartRefreshPipeline:

    @pytest.mark.asyncio
    async def test_refresh_no_blueprint_returns_no_refresh(self, mock_settings):
        storage = AsyncMock()
        storage.exists = AsyncMock(return_value=False)
        svc = SmartRefreshService(storage=storage, settings=mock_settings)

        result = await svc.refresh("no-repo", ["src/api/routes.py"], "/tmp/project")
        assert result.status == "no_refresh_needed"

    @pytest.mark.asyncio
    async def test_refresh_no_source_files_returns_no_refresh(self, service):
        result = await service.refresh("repo-123", ["README.md", "docs/guide.md"], "/tmp/project")
        assert result.status == "no_refresh_needed"

    @pytest.mark.asyncio
    async def test_refresh_no_covered_folders_returns_no_refresh(self, service):
        result = await service.refresh("repo-123", ["lib/utils.py"], "/tmp/project")
        assert result.status == "no_refresh_needed"

    @pytest.mark.asyncio
    async def test_refresh_aligned_no_warnings(self, service, tmp_path):
        # Write a source file so _read_local_file can find it
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "user_routes.py").write_text("from fastapi import APIRouter")

        ai_response = _make_ai_response([{
            "path": "src/api",
            "aligned": True,
            "warnings": [],
            "claude_md_stale": False,
            "suggestion": "",
        }])
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=ai_response)
        service._ai_client = mock_client

        result = await service.refresh(
            "repo-123",
            ["src/api/user_routes.py"],
            str(tmp_path),
        )
        assert result.status == "no_refresh_needed"
        assert result.warnings == []

    @pytest.mark.asyncio
    async def test_refresh_with_warnings(self, service, tmp_path):
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "user_routes.py").write_text("import something")

        ai_response = _make_ai_response([{
            "path": "src/api",
            "aligned": False,
            "warnings": [{
                "severity": "warning",
                "message": "File violates placement rule",
                "rule_violated": "route placement",
                "suggestion": "Move to correct directory",
            }],
            "claude_md_stale": False,
            "suggestion": "",
        }])
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=ai_response)
        service._ai_client = mock_client

        result = await service.refresh("repo-123", ["src/api/user_routes.py"], str(tmp_path))
        assert result.status == "warnings"
        assert len(result.warnings) == 1
        assert result.warnings[0].severity == "warning"
        assert result.warnings[0].folder == "src/api"

    @pytest.mark.asyncio
    async def test_refresh_stale_triggers_regeneration(self, service_with_intent, tmp_path):
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "user_routes.py").write_text("code")

        ai_response = _make_ai_response([{
            "path": "src/api",
            "aligned": True,
            "warnings": [],
            "claude_md_stale": True,
            "suggestion": "",
        }])
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=ai_response)
        service_with_intent._ai_client = mock_client

        with patch("application.services.smart_refresh_service.LocalPushClient") as MockPush:
            MockPush.return_value.write_files.return_value = ["src/api/CLAUDE.md"]

            result = await service_with_intent.refresh(
                "repo-123",
                ["src/api/user_routes.py"],
                str(tmp_path),
            )

        assert result.status == "refreshed"
        assert "src/api/CLAUDE.md" in result.updated_files

    @pytest.mark.asyncio
    async def test_refresh_ai_failure_returns_info_warnings(self, service, tmp_path):
        api_dir = tmp_path / "src" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "user_routes.py").write_text("code")

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))
        service._ai_client = mock_client

        with patch("application.services.smart_refresh_service.LocalPushClient") as MockPush:
            MockPush.return_value.write_files.return_value = []

            result = await service.refresh("repo-123", ["src/api/user_routes.py"], str(tmp_path))

        # AI failure results in info-level warnings
        assert len(result.warnings) >= 1
        assert result.warnings[0].severity == "info"
        assert "unavailable" in result.warnings[0].message.lower()

    @pytest.mark.asyncio
    async def test_refresh_batches_folders_over_max(self, service, tmp_path):
        """When > _MAX_FOLDERS_PER_BATCH folders are affected, AI is called multiple times."""
        # Create a blueprint with 10 components
        components = []
        for i in range(10):
            loc = f"src/mod{i}"
            components.append(Component(
                name=f"Mod{i}",
                location=loc,
                responsibility=f"Module {i}",
            ))
            d = tmp_path / loc
            d.mkdir(parents=True, exist_ok=True)
            (d / "code.py").write_text(f"# mod {i}")

        blueprint = StructuredBlueprint(
            meta=BlueprintMeta(repository="acme/big", repository_id="big-repo", architecture_style="modular"),
            components=Components(structure_type="modular", components=components),
        )
        bp_json = json.dumps(blueprint.model_dump()).encode("utf-8")

        async def _exists(path):
            return path == "blueprints/big-repo/blueprint.json"

        async def _read(path):
            if path == "blueprints/big-repo/blueprint.json":
                return bp_json
            raise FileNotFoundError(path)

        service._storage.exists = AsyncMock(side_effect=_exists)
        service._storage.read = AsyncMock(side_effect=_read)

        # AI returns aligned for all folders
        def make_response(*args, **kwargs):
            return _make_ai_response([{"path": "x", "aligned": True, "warnings": [], "claude_md_stale": False, "suggestion": ""}])

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=make_response)
        service._ai_client = mock_client

        changed = [f"src/mod{i}/code.py" for i in range(10)]
        await service.refresh("big-repo", changed, str(tmp_path))

        # With 10 folders and batch size 8, we expect 2 AI calls
        assert mock_client.messages.create.call_count == 2


# ── _compute_affected_folders Tests ───────────────────────────────────────────


class TestComputeAffectedFolders:

    def test_file_in_covered_folder_is_affected(self):
        covered = {"src/api": {}, "src/services": {}}
        result = SmartRefreshService._compute_affected_folders(
            ["src/api/routes.py"], covered,
        )
        assert "src/api" in result

    def test_file_in_uncovered_folder_is_not_affected(self):
        covered = {"src/api": {}, "src/services": {}}
        result = SmartRefreshService._compute_affected_folders(
            ["lib/utils.py"], covered,
        )
        assert len(result) == 0

    def test_ancestor_folder_matching(self):
        """A file nested deeper than the covered folder still matches the ancestor."""
        covered = {"src/api": {}}
        result = SmartRefreshService._compute_affected_folders(
            ["src/api/v2/routes.py"], covered,
        )
        assert "src/api" in result

    def test_root_level_file(self):
        """Files at root level have '.' parent which is normalized to ''."""
        covered = {"src/api": {}}
        result = SmartRefreshService._compute_affected_folders(
            ["main.py"], covered,
        )
        assert len(result) == 0


# ── _is_source_file Tests ────────────────────────────────────────────────────


class TestIsSourceFile:

    def test_python_file_is_source(self):
        assert _is_source_file("src/api/routes.py") is True

    def test_markdown_not_source(self):
        assert _is_source_file("README.md") is False

    def test_typescript_is_source(self):
        assert _is_source_file("src/components/App.tsx") is True

    def test_json_not_source(self):
        assert _is_source_file("package.json") is False

    def test_swift_is_source(self):
        assert _is_source_file("Sources/App.swift") is True


# ── _read_local_file Tests ───────────────────────────────────────────────────


class TestReadLocalFile:

    def test_reads_existing_file(self, tmp_path):
        (tmp_path / "hello.py").write_text("print('hi')")
        result = _read_local_file(str(tmp_path), "hello.py")
        assert result == "print('hi')"

    def test_returns_none_for_missing(self, tmp_path):
        result = _read_local_file(str(tmp_path), "nope.py")
        assert result is None

    def test_rejects_path_traversal(self, tmp_path):
        result = _read_local_file(str(tmp_path), "../../etc/passwd")
        assert result is None


# ── _call_ai Tests ───────────────────────────────────────────────────────────


class TestCallAi:

    @pytest.mark.asyncio
    async def test_parses_clean_json(self, service):
        response = _make_ai_response([{"path": "src/api", "aligned": True}])
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=response)
        service._ai_client = mock_client

        result = await service._call_ai("test prompt")
        assert result["folders"][0]["path"] == "src/api"

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self, service):
        text = '```json\n{"folders": [{"path": "x"}]}\n```'
        response = MagicMock(content=[MagicMock(text=text)])
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=response)
        service._ai_client = mock_client

        result = await service._call_ai("test prompt")
        assert result["folders"][0]["path"] == "x"


# ── _regenerate_claude_md Tests ──────────────────────────────────────────────


class TestRegenerateClaudeMd:

    @pytest.mark.asyncio
    async def test_uses_intent_layer_service_when_available(
        self, service_with_intent, sample_blueprint, tmp_path,
    ):
        with patch("application.services.smart_refresh_service.LocalPushClient") as MockPush:
            MockPush.return_value.write_files.return_value = ["src/api/CLAUDE.md"]

            updated = await service_with_intent._regenerate_claude_md(
                repo_id="repo-123",
                blueprint=sample_blueprint,
                stale_folders=["src/api"],
                target_local_path=str(tmp_path),
            )

        assert "src/api/CLAUDE.md" in updated
        service_with_intent._intent_layer_service.preview.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_deterministic_on_failure(
        self, mock_storage, mock_settings, sample_blueprint, tmp_path,
    ):
        failing_intent = AsyncMock()
        failing_intent.preview = AsyncMock(side_effect=Exception("boom"))
        svc = SmartRefreshService(
            storage=mock_storage,
            settings=mock_settings,
            intent_layer_service=failing_intent,
        )

        with patch("application.services.smart_refresh_service.LocalPushClient") as MockPush:
            MockPush.return_value.write_files.return_value = ["src/api/CLAUDE.md"]

            updated = await svc._regenerate_claude_md(
                repo_id="repo-123",
                blueprint=sample_blueprint,
                stale_folders=["src/api"],
                target_local_path=str(tmp_path),
            )

        # Should have fallen back to deterministic rendering
        assert "src/api/CLAUDE.md" in updated
