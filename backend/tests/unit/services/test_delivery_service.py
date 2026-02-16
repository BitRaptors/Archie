"""Tests for DeliveryService."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.blueprint import BlueprintMeta, StructuredBlueprint
from domain.exceptions.domain_exceptions import ValidationError
from application.services.delivery_service import (
    DeliveryService,
    _merge_markdown,
    _merge_json_config,
)


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
    client.get_file_content.return_value = None  # No existing files by default
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


class TestMarkdownMerge:

    def test_merge_no_existing_file(self):
        result = _merge_markdown(None, "# Generated", "repo")
        assert result == "<!-- gbr:start repo=repo -->\n# Generated\n<!-- gbr:end -->"

    def test_merge_existing_without_markers(self):
        existing = "# My Custom Docs\nSome user content."
        result = _merge_markdown(existing, "# Generated", "repo")
        assert result.startswith("# My Custom Docs\nSome user content.")
        assert "<!-- gbr:start repo=repo -->" in result
        assert "# Generated" in result
        assert "<!-- gbr:end -->" in result

    def test_merge_existing_with_markers(self):
        existing = (
            "# User header\n\n"
            "<!-- gbr:start repo=repo -->\n"
            "Old generated content\n"
            "<!-- gbr:end -->\n\n"
            "# User footer"
        )
        result = _merge_markdown(existing, "New generated content", "repo")
        assert "# User header" in result
        assert "# User footer" in result
        assert "New generated content" in result
        assert "Old generated content" not in result

    def test_merge_markers_in_middle(self):
        existing = (
            "Line above\n"
            "<!-- gbr:start repo=repo -->\n"
            "middle stuff\n"
            "<!-- gbr:end -->\n"
            "Line below"
        )
        result = _merge_markdown(existing, "REPLACED", "repo")
        assert result.startswith("Line above\n")
        assert result.endswith("\nLine below")
        assert "REPLACED" in result
        assert "middle stuff" not in result


class TestJsonConfigMerge:

    def test_merge_no_existing_file(self):
        config = {"mcpServers": {"architecture-blueprints": {"url": "http://localhost:8000/mcp/sse"}}}
        result = json.loads(_merge_json_config(None, config))
        assert result == config

    def test_merge_existing_with_other_servers(self):
        existing = json.dumps({
            "mcpServers": {
                "my-custom-server": {"url": "http://localhost:3000"}
            }
        })
        config = {"mcpServers": {"architecture-blueprints": {"url": "http://localhost:8000/mcp/sse"}}}
        result = json.loads(_merge_json_config(existing, config))
        assert "my-custom-server" in result["mcpServers"]
        assert "architecture-blueprints" in result["mcpServers"]

    def test_merge_existing_with_our_key(self):
        existing = json.dumps({
            "mcpServers": {
                "other-server": {"url": "http://other"},
                "architecture-blueprints": {"url": "http://old-url"}
            }
        })
        config = {"mcpServers": {"architecture-blueprints": {"url": "http://new-url"}}}
        result = json.loads(_merge_json_config(existing, config))
        assert result["mcpServers"]["other-server"]["url"] == "http://other"
        assert result["mcpServers"]["architecture-blueprints"]["url"] == "http://new-url"

    def test_merge_invalid_json(self):
        config = {"mcpServers": {"architecture-blueprints": {"url": "http://localhost:8000/mcp/sse"}}}
        result = json.loads(_merge_json_config("not valid json {{{", config))
        assert result == config


class TestApplyWithMerge:

    @pytest.mark.asyncio
    async def test_apply_reads_existing_files_before_commit(
        self, service, mock_push_client
    ):
        with patch(
            "application.services.delivery_service.GitHubPushClient",
            return_value=mock_push_client,
        ):
            await service.apply(
                source_repo_id="repo-uuid-123",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["claude_md", "agents_md"],
                strategy="commit",
            )

        # get_file_content should be called once per output file
        assert mock_push_client.get_file_content.call_count == 2

    @pytest.mark.asyncio
    async def test_apply_merges_markdown_with_existing(
        self, service, mock_push_client
    ):
        user_content = "# My Custom Notes\nDo not remove this."
        mock_push_client.get_file_content.return_value = user_content

        with patch(
            "application.services.delivery_service.GitHubPushClient",
            return_value=mock_push_client,
        ):
            await service.apply(
                source_repo_id="repo-uuid-123",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["claude_md"],
                strategy="commit",
            )

        committed_files = mock_push_client.commit_files.call_args[0][2]
        merged = committed_files["CLAUDE.md"]
        assert "# My Custom Notes" in merged
        assert "Do not remove this." in merged
        assert "<!-- gbr:start repo=repo -->" in merged
        assert "<!-- gbr:end -->" in merged

    @pytest.mark.asyncio
    async def test_apply_merges_json_with_existing_servers(
        self, service, mock_push_client
    ):
        existing_json = json.dumps({
            "mcpServers": {
                "my-other-server": {"url": "http://localhost:5000"}
            }
        })
        mock_push_client.get_file_content.return_value = existing_json

        with patch(
            "application.services.delivery_service.GitHubPushClient",
            return_value=mock_push_client,
        ):
            await service.apply(
                source_repo_id="repo-uuid-123",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["mcp_claude"],
                strategy="commit",
            )

        committed_files = mock_push_client.commit_files.call_args[0][2]
        merged = json.loads(committed_files[".mcp.json"])
        assert "my-other-server" in merged["mcpServers"]
        assert "architecture-blueprints" in merged["mcpServers"]
