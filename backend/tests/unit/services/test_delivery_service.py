"""Tests for DeliveryService."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.blueprint import BlueprintMeta, StructuredBlueprint
from domain.exceptions.domain_exceptions import ValidationError
from application.services.delivery_service import (
    DeliveryService,
    VALID_OUTPUTS,
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
    """Mock storage with blueprint + pre-generated intent layer files."""
    from application.services.agent_file_generator import generate_all
    agent_output = generate_all(sample_blueprint)
    agent_files = agent_output.to_file_map()  # {CLAUDE.md, AGENTS.md, .claude/rules/*, .cursor/rules/*}

    bp_json = json.dumps(sample_blueprint.model_dump()).encode("utf-8")
    il_base = "blueprints/repo-uuid-123/intent_layer"

    # Build storage path -> content map for intent layer files
    il_stored: dict[str, bytes] = {}
    for rel_path, content in agent_files.items():
        il_stored[f"{il_base}/{rel_path}"] = content.encode("utf-8")

    all_il_paths = list(il_stored.keys())

    async def _exists(path):
        if path == "blueprints/repo-uuid-123/blueprint.json":
            return True
        if path == f"{il_base}/CLAUDE.md":
            return True
        return False

    async def _read(path):
        if path == "blueprints/repo-uuid-123/blueprint.json":
            return bp_json
        if path in il_stored:
            return il_stored[path]
        raise FileNotFoundError(path)

    async def _list_files(prefix):
        if prefix == il_base:
            return all_il_paths
        return []

    storage = AsyncMock()
    storage.exists = AsyncMock(side_effect=_exists)
    storage.read = AsyncMock(side_effect=_read)
    storage.list_files = AsyncMock(side_effect=_list_files)
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


class TestValidOutputs:

    def test_valid_outputs_includes_aggregate_keys(self):
        assert "claude_rules" in VALID_OUTPUTS
        assert "cursor_rules" in VALID_OUTPUTS

    def test_valid_outputs_includes_static_keys(self):
        assert "claude_md" in VALID_OUTPUTS
        assert "agents_md" in VALID_OUTPUTS
        assert "mcp_claude" in VALID_OUTPUTS
        assert "mcp_cursor" in VALID_OUTPUTS

    def test_valid_outputs_includes_codebase_map(self):
        assert "codebase_map" in VALID_OUTPUTS

    def test_valid_outputs_includes_intent_layer(self):
        assert "intent_layer" in VALID_OUTPUTS


class TestPreview:

    @pytest.mark.asyncio
    async def test_preview_returns_selected_outputs(self, service):
        result = await service.preview("repo-uuid-123", ["claude_md", "agents_md"])
        assert "CLAUDE.md" in result
        assert "AGENTS.md" in result
        assert "# CLAUDE.md" in result["CLAUDE.md"]
        assert "# AGENTS.md" in result["AGENTS.md"]

    @pytest.mark.asyncio
    async def test_preview_claude_rules_aggregate(self, service):
        result = await service.preview("repo-uuid-123", ["claude_rules"])
        claude_rule_paths = [k for k in result if k.startswith(".claude/rules/")]
        assert len(claude_rule_paths) > 0
        # MCP tools always present
        assert ".claude/rules/mcp-tools.md" in result

    @pytest.mark.asyncio
    async def test_preview_cursor_rules_aggregate(self, service):
        result = await service.preview("repo-uuid-123", ["cursor_rules"])
        cursor_rule_paths = [k for k in result if k.startswith(".cursor/rules/")]
        assert len(cursor_rule_paths) > 0
        assert ".cursor/rules/mcp-tools.md" in result

    @pytest.mark.asyncio
    async def test_preview_raises_when_blueprint_not_found(self):
        storage = AsyncMock()
        storage.exists = AsyncMock(return_value=False)
        service = DeliveryService(storage=storage)
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
        commit_call_files = mock_push_client.commit_files.call_args[0][2]
        assert list(commit_call_files.keys()) == ["CLAUDE.md"]

    @pytest.mark.asyncio
    async def test_apply_delivers_split_rule_files(self, service, mock_push_client):
        with patch(
            "application.services.delivery_service.GitHubPushClient",
            return_value=mock_push_client,
        ):
            result = await service.apply(
                source_repo_id="repo-uuid-123",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["claude_rules"],
                strategy="commit",
            )

        # Should deliver .claude/rules/ files
        claude_rule_paths = [p for p in result.files_delivered if p.startswith(".claude/rules/")]
        assert len(claude_rule_paths) > 0
        assert ".claude/rules/mcp-tools.md" in result.files_delivered

        commit_call_files = mock_push_client.commit_files.call_args[0][2]
        assert ".claude/rules/mcp-tools.md" in commit_call_files

    @pytest.mark.asyncio
    async def test_apply_raises_when_blueprint_not_found(self, mock_push_client):
        storage = AsyncMock()
        storage.exists = AsyncMock(return_value=False)
        service = DeliveryService(storage=storage)
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

    @pytest.mark.asyncio
    async def test_backward_compat_cursor_rules_key(self, service, mock_push_client):
        """cursor_rules key should expand to .cursor/rules/ files."""
        with patch(
            "application.services.delivery_service.GitHubPushClient",
            return_value=mock_push_client,
        ):
            result = await service.apply(
                source_repo_id="repo-uuid-123",
                target_repo_full_name="owner/repo",
                token="test-token",
                outputs=["cursor_rules"],
                strategy="commit",
            )

        cursor_paths = [p for p in result.files_delivered if p.startswith(".cursor/rules/")]
        assert len(cursor_paths) > 0


class TestMcpConfigGeneration:

    @pytest.mark.asyncio
    async def test_preview_mcp_configs(self, service):
        result = await service.preview("repo-uuid-123", ["mcp_claude", "mcp_cursor"])
        assert ".mcp.json" in result
        assert ".cursor/mcp.json" in result

        # Both should be valid JSON with the same content
        claude_config = json.loads(result[".mcp.json"])
        cursor_config = json.loads(result[".cursor/mcp.json"])
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
