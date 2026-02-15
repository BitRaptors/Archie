"""Tests for DeliveryService."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.blueprint import BlueprintMeta, StructuredBlueprint
from domain.exceptions.domain_exceptions import ValidationError
from application.services.delivery_service import DeliveryService


@pytest.fixture
def sample_blueprint() -> StructuredBlueprint:
    return StructuredBlueprint(
        meta=BlueprintMeta(
            repository="acme/backend-api",
            repository_id="repo-uuid-123",
        ),
    )


@pytest.fixture
def mock_storage(sample_blueprint):
    """Mock storage that returns a blueprint."""
    storage = AsyncMock()
    storage.exists = AsyncMock(return_value=True)
    storage.read = AsyncMock(
        return_value=json.dumps(sample_blueprint.model_dump()).encode("utf-8")
    )
    return storage


@pytest.fixture
def service(mock_storage):
    return DeliveryService(storage=mock_storage)


@pytest.fixture
def mock_push_client():
    client = MagicMock()
    client.get_default_branch.return_value = "main"
    client.create_branch.return_value = "refs/heads/gbr/sync-architecture-outputs"
    client.commit_files.return_value = "sha-abc123"
    client.create_pull_request.return_value = {
        "url": "https://github.com/owner/repo/pull/42",
        "number": 42,
    }
    return client


class TestPreview:

    @pytest.mark.asyncio
    async def test_preview_returns_selected_outputs(self, service):
        result = await service.preview("repo-uuid-123", ["claude_md", "agents_md"])
        assert "claude_md" in result
        assert "agents_md" in result
        assert "cursor_rules" not in result
        assert "# CLAUDE.md" in result["claude_md"]
        assert "# AGENTS.md" in result["agents_md"]

    @pytest.mark.asyncio
    async def test_preview_raises_when_blueprint_not_found(self, service, mock_storage):
        mock_storage.exists = AsyncMock(return_value=False)
        with pytest.raises(ValidationError, match="Blueprint not found"):
            await service.preview("missing-repo", ["claude_md"])

    @pytest.mark.asyncio
    async def test_preview_raises_on_unknown_output(self, service):
        with pytest.raises(ValidationError, match="Unknown output type"):
            await service.preview("repo-uuid-123", ["invalid_key"])


class TestApply:

    @pytest.mark.asyncio
    async def test_apply_pr_strategy_creates_branch_and_pr(
        self, service, mock_push_client
    ):
        with patch(
            "application.services.delivery_service.GitHubPushClient",
            return_value=mock_push_client,
        ):
            result = await service.apply(
                source_repo_id="repo-uuid-123",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["claude_md", "agents_md"],
                strategy="pr",
            )

        assert result.status == "success"
        assert result.strategy == "pr"
        assert result.pr_url == "https://github.com/owner/repo/pull/42"
        assert result.branch == "gbr/sync-architecture-outputs"
        assert "CLAUDE.md" in result.files_delivered
        assert "AGENTS.md" in result.files_delivered

        mock_push_client.create_branch.assert_called_once()
        mock_push_client.commit_files.assert_called_once()
        mock_push_client.create_pull_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_commit_strategy_commits_directly(
        self, service, mock_push_client
    ):
        with patch(
            "application.services.delivery_service.GitHubPushClient",
            return_value=mock_push_client,
        ):
            result = await service.apply(
                source_repo_id="repo-uuid-123",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["claude_md"],
                strategy="commit",
            )

        assert result.status == "success"
        assert result.strategy == "commit"
        assert result.commit_sha == "sha-abc123"
        assert result.branch == "main"

        mock_push_client.create_branch.assert_not_called()
        mock_push_client.create_pull_request.assert_not_called()
        mock_push_client.commit_files.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_respects_output_selection(self, service, mock_push_client):
        with patch(
            "application.services.delivery_service.GitHubPushClient",
            return_value=mock_push_client,
        ):
            result = await service.apply(
                source_repo_id="repo-uuid-123",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["claude_md"],
                strategy="commit",
            )

        assert result.files_delivered == ["CLAUDE.md"]
        # Verify only CLAUDE.md was in the committed files
        commit_call_files = mock_push_client.commit_files.call_args[0][2]
        assert list(commit_call_files.keys()) == ["CLAUDE.md"]

    @pytest.mark.asyncio
    async def test_apply_raises_when_blueprint_not_found(
        self, service, mock_storage, mock_push_client
    ):
        mock_storage.exists = AsyncMock(return_value=False)
        with pytest.raises(ValidationError, match="Blueprint not found"):
            await service.apply(
                source_repo_id="missing",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["claude_md"],
            )

    @pytest.mark.asyncio
    async def test_apply_raises_on_invalid_strategy(self, service):
        with pytest.raises(ValidationError, match="Invalid strategy"):
            await service.apply(
                source_repo_id="repo-uuid-123",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["claude_md"],
                strategy="invalid",
            )

    @pytest.mark.asyncio
    async def test_apply_includes_mcp_configs(self, service, mock_push_client):
        with patch(
            "application.services.delivery_service.GitHubPushClient",
            return_value=mock_push_client,
        ):
            result = await service.apply(
                source_repo_id="repo-uuid-123",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["mcp_claude", "mcp_cursor"],
                strategy="commit",
            )

        assert ".mcp.json" in result.files_delivered
        assert ".cursor/mcp.json" in result.files_delivered

        commit_call_files = mock_push_client.commit_files.call_args[0][2]
        mcp_content = commit_call_files[".mcp.json"]
        parsed = json.loads(mcp_content)
        assert "mcpServers" in parsed
        assert "architecture-blueprints" in parsed["mcpServers"]
        assert parsed["mcpServers"]["architecture-blueprints"]["url"] == "http://localhost:8000/mcp/sse"


class TestMcpConfigGeneration:

    @pytest.mark.asyncio
    async def test_preview_mcp_configs(self, service):
        result = await service.preview("repo-uuid-123", ["mcp_claude", "mcp_cursor"])
        assert "mcp_claude" in result
        assert "mcp_cursor" in result

        # Both should be valid JSON with the same content
        claude_config = json.loads(result["mcp_claude"])
        cursor_config = json.loads(result["mcp_cursor"])
        assert claude_config == cursor_config
        assert "mcpServers" in claude_config
        assert claude_config["mcpServers"]["architecture-blueprints"]["url"] == "http://localhost:8000/mcp/sse"
