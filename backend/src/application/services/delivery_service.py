"""Delivery service -- push architecture outputs to a target GitHub repository."""
import json
import re
from dataclasses import dataclass
from typing import Optional

from domain.entities.blueprint import StructuredBlueprint
from domain.exceptions.domain_exceptions import ValidationError
from application.services.agent_file_generator import (
    generate_all,
    generate_claude_md,
    generate_cursor_rules,
    generate_agents_md,
)
from infrastructure.external.github_push_client import GitHubPushClient


# ---------------------------------------------------------------------------
# Static file map (non-rule outputs)
# ---------------------------------------------------------------------------

_STATIC_FILE_MAP: dict[str, str] = {
    "claude_md": "CLAUDE.md",
    "agents_md": "AGENTS.md",
    "mcp_claude": ".mcp.json",
    "mcp_cursor": ".cursor/mcp.json",
}

# Aggregate keys that expand into multiple rule files
_AGGREGATE_KEYS = {"claude_rules", "cursor_rules"}

# All valid output keys (static + aggregate)
VALID_OUTPUTS = set(_STATIC_FILE_MAP.keys()) | _AGGREGATE_KEYS

# Merge strategy per output key
_STATIC_MERGE_STRATEGY: dict[str, str] = {
    "claude_md": "markdown",
    "agents_md": "markdown",
    "mcp_claude": "json",
    "mcp_cursor": "json",
}

# MCP server config (same content for both Claude Code and Cursor)
_MCP_CONFIG = json.dumps(
    {
        "mcpServers": {
            "architecture-blueprints": {
                "url": "http://localhost:8000/mcp/sse"
            }
        }
    },
    indent=2,
)


def _generate_mcp_config(_blueprint: StructuredBlueprint) -> str:
    """Generate MCP server config JSON. Same for both Claude Code and Cursor."""
    return _MCP_CONFIG


_MARKER_PATTERN = re.compile(
    r"<!-- gbr:start repo=.+? -->\n.*?\n<!-- gbr:end -->",
    re.DOTALL,
)


def _merge_markdown(existing: str | None, generated: str, repo_name: str) -> str:
    """Merge generated markdown into an existing file using fenced markers.

    - If no existing file -> wrap generated content in markers.
    - If markers found -> replace only the content between markers.
    - If no markers found -> append fenced block at end.
    """
    start_marker = f"<!-- gbr:start repo={repo_name} -->"
    end_marker = "<!-- gbr:end -->"
    fenced = f"{start_marker}\n{generated}\n{end_marker}"

    if existing is None:
        return fenced

    if _MARKER_PATTERN.search(existing):
        return _MARKER_PATTERN.sub(fenced, existing)

    # No markers yet -- append to the end
    separator = "\n\n" if not existing.endswith("\n") else "\n"
    return existing + separator + fenced


def _merge_json_config(existing: str | None, generated_config: dict) -> str:
    """Merge generated MCP config into an existing JSON file.

    Only upserts the ``mcpServers.architecture-blueprints`` key -- all other
    keys in the existing file are preserved.
    """
    if existing is None:
        return json.dumps(generated_config, indent=2)

    try:
        data = json.loads(existing)
    except (json.JSONDecodeError, ValueError):
        return json.dumps(generated_config, indent=2)

    # Deep-merge only our key under mcpServers
    our_servers = generated_config.get("mcpServers", {})
    if "mcpServers" not in data:
        data["mcpServers"] = {}
    for key, value in our_servers.items():
        data["mcpServers"][key] = value

    return json.dumps(data, indent=2)


@dataclass
class DeliveryResult:
    status: str
    strategy: str
    files_delivered: list[str]
    branch: Optional[str] = None
    pr_url: Optional[str] = None
    commit_sha: Optional[str] = None


class DeliveryService:
    """Orchestrates pushing architecture outputs to a target GitHub repository."""

    def __init__(self, storage):
        self._storage = storage

    async def preview(
        self,
        source_repo_id: str,
        outputs: list[str],
    ) -> dict[str, str]:
        """Generate and return selected outputs without pushing."""
        blueprint = await self._load_blueprint(source_repo_id)
        return self._generate_outputs(blueprint, outputs)

    async def apply(
        self,
        source_repo_id: str,
        target_repo_full_name: str,
        token: str,
        outputs: list[str],
        strategy: str = "pr",
        branch_prefix: str = "gbr",
    ) -> DeliveryResult:
        """Generate outputs and push them to the target repository."""
        if strategy not in ("pr", "commit"):
            raise ValidationError(f"Invalid strategy: {strategy}. Must be 'pr' or 'commit'.")

        blueprint = await self._load_blueprint(source_repo_id)
        generated = self._generate_outputs(blueprint, outputs)

        push_client = GitHubPushClient(token)
        default_branch = push_client.get_default_branch(target_repo_full_name)

        # Build file map with merge: read existing content, then merge
        repo_name = target_repo_full_name.split("/")[-1] if "/" in target_repo_full_name else target_repo_full_name
        files: dict[str, str] = {}
        for path, content in generated.items():
            existing = push_client.get_file_content(target_repo_full_name, path, default_branch)
            merge_strategy = self._get_merge_strategy(path)
            if merge_strategy == "markdown":
                files[path] = _merge_markdown(existing, content, repo_name)
            elif merge_strategy == "json":
                generated_config = json.loads(content)
                files[path] = _merge_json_config(existing, generated_config)
            else:
                files[path] = content
        delivered_paths = list(files.keys())

        if strategy == "pr":
            branch_name = f"{branch_prefix}/sync-architecture-outputs"
            push_client.create_branch(target_repo_full_name, branch_name, default_branch)
            push_client.commit_files(
                target_repo_full_name,
                branch_name,
                files,
                "chore: sync architecture outputs from blueprint analysis",
            )
            pr = push_client.create_pull_request(
                target_repo_full_name,
                branch_name,
                default_branch,
                title="Sync architecture outputs",
                body=self._build_pr_body(delivered_paths, source_repo_id),
            )
            return DeliveryResult(
                status="success",
                strategy="pr",
                branch=branch_name,
                pr_url=pr["url"],
                files_delivered=delivered_paths,
            )
        else:
            sha = push_client.commit_files(
                target_repo_full_name,
                default_branch,
                files,
                "chore: sync architecture outputs from blueprint analysis",
            )
            return DeliveryResult(
                status="success",
                strategy="commit",
                branch=default_branch,
                commit_sha=sha,
                files_delivered=delivered_paths,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _load_blueprint(self, repo_id: str) -> StructuredBlueprint:
        """Load a structured blueprint from storage."""
        json_path = f"blueprints/{repo_id}/blueprint.json"
        try:
            if await self._storage.exists(json_path):
                content = await self._storage.read(json_path)
                text = content.decode("utf-8") if isinstance(content, bytes) else content
                data = json.loads(text)
                return StructuredBlueprint.model_validate(data)
        except Exception:
            pass
        raise ValidationError(f"Blueprint not found for repository {repo_id}")

    @staticmethod
    def _get_merge_strategy(path: str) -> str:
        """Determine merge strategy from file path."""
        if path.endswith(".json"):
            return "json"
        if path.endswith(".md"):
            return "markdown"
        return "overwrite"

    def _generate_outputs(
        self,
        blueprint: StructuredBlueprint,
        outputs: list[str],
    ) -> dict[str, str]:
        """Generate selected output files from a blueprint.

        Returns ``{file_path: content}`` -- aggregate keys (``claude_rules``,
        ``cursor_rules``) are expanded into individual rule file entries.
        """
        # Validate all keys first
        for key in outputs:
            if key not in VALID_OUTPUTS:
                raise ValidationError(f"Unknown output type: {key}. Valid: {VALID_OUTPUTS}")

        gen_output = generate_all(blueprint)
        result: dict[str, str] = {}

        for key in outputs:
            if key == "claude_md":
                result["CLAUDE.md"] = gen_output.claude_md
            elif key == "agents_md":
                result["AGENTS.md"] = gen_output.agents_md
            elif key == "mcp_claude":
                result[".mcp.json"] = _generate_mcp_config(blueprint)
            elif key == "mcp_cursor":
                result[".cursor/mcp.json"] = _generate_mcp_config(blueprint)
            elif key == "claude_rules":
                for rf in gen_output.rule_files:
                    result[rf.claude_path] = rf.render_claude()
            elif key == "cursor_rules":
                for rf in gen_output.rule_files:
                    result[rf.cursor_path] = rf.render_cursor()

        return result

    @staticmethod
    def _build_pr_body(files: list[str], source_repo_id: str) -> str:
        file_list = "\n".join(f"- `{f}`" for f in files)
        return (
            "## Architecture Outputs\n\n"
            f"Auto-generated from blueprint analysis (source: `{source_repo_id}`).\n\n"
            f"### Files\n{file_list}\n\n"
            "---\n"
            "Generated by [Architecture MCP](https://github.com/your-org/architecture-mcp)"
        )
