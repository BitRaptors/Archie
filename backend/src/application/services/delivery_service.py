"""Delivery service -- push architecture outputs to a target GitHub repository."""
import json
import re
from dataclasses import dataclass
from typing import Optional

from domain.entities.blueprint import StructuredBlueprint
from domain.exceptions.domain_exceptions import ValidationError
from infrastructure.external.github_push_client import GitHubPushClient
from infrastructure.external.local_push_client import LocalPushClient


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

# All valid output keys (static + aggregate + async)
VALID_OUTPUTS = set(_STATIC_FILE_MAP.keys()) | _AGGREGATE_KEYS | {"intent_layer", "codebase_map", "claude_hooks"}

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
            "archie": {
                "type": "http",
                "url": "http://localhost:8000/mcp/"
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

    Only upserts the ``mcpServers.archie`` key -- all other
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


def _merge_settings_json(existing: str | None, generated_hooks: dict) -> str:
    """Merge hooks config into an existing .claude/settings.json.

    Only upserts the ``hooks`` key -- all other keys (permissions, etc.)
    are preserved.  Within hooks, replaces per event type.
    """
    if existing is None:
        return json.dumps(generated_hooks, indent=2)

    try:
        data = json.loads(existing)
    except (json.JSONDecodeError, ValueError):
        return json.dumps(generated_hooks, indent=2)

    our_hooks = generated_hooks.get("hooks", {})
    if "hooks" not in data:
        data["hooks"] = {}
    for event_type, entries in our_hooks.items():
        data["hooks"][event_type] = entries

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

    def __init__(self, storage, settings=None):
        self._storage = storage
        self._settings = settings

    async def preview(
        self,
        source_repo_id: str,
        outputs: list[str],
    ) -> dict[str, str]:
        """Generate and return selected outputs without pushing."""
        for key in outputs:
            if key not in VALID_OUTPUTS:
                raise ValidationError(f"Unknown output type: {key}. Valid: {VALID_OUTPUTS}")

        result: dict[str, str] = {}

        # Check if any non-MCP outputs are requested (those come from the intent layer)
        needs_il = any(
            k in outputs
            for k in ("claude_md", "agents_md", "claude_rules", "cursor_rules", "intent_layer", "codebase_map")
        )

        if needs_il:
            # Load pre-generated files from storage (saved during analysis pipeline)
            all_files = await self._load_intent_layer_files(source_repo_id)
            if not all_files:
                raise ValidationError(f"Blueprint not found for repository {source_repo_id}")
            for path, content in all_files.items():
                if self._should_include(path, outputs):
                    result[path] = content

        # Hook scripts + .archie config for the target project
        if "claude_hooks" in outputs:
            from application.services.hook_assets import get_hook_files
            hook_kwargs = {}
            if self._settings:
                hook_kwargs = {
                    "repo_id": source_repo_id,
                    "backend_url": f"http://{self._settings.host}:{self._settings.port}",
                    "storage_path": self._settings.storage_path,
                }
            for path, content in get_hook_files(**hook_kwargs).items():
                result[path] = content

        # MCP configs are not part of the intent layer
        if "mcp_claude" in outputs or "mcp_cursor" in outputs:
            blueprint = await self._load_blueprint(source_repo_id)
            if "mcp_claude" in outputs:
                result[".mcp.json"] = _generate_mcp_config(blueprint)
            if "mcp_cursor" in outputs:
                result[".cursor/mcp.json"] = _generate_mcp_config(blueprint)

        return result

    async def apply(
        self,
        source_repo_id: str,
        target_repo_full_name: str,
        token: str,
        outputs: list[str],
        strategy: str = "pr",
        branch_prefix: str = "gbr",
        target_local_path: Optional[str] = None,
    ) -> DeliveryResult:
        """Generate outputs and push them to the target repository or local path."""
        if strategy not in ("pr", "commit", "local"):
            raise ValidationError(f"Invalid strategy: {strategy}. Must be 'pr', 'commit', or 'local'.")

        if strategy == "local":
            return await self._apply_local(source_repo_id, outputs, target_local_path)

        generated = await self.preview(source_repo_id, outputs)

        push_client = GitHubPushClient(token)
        default_branch = push_client.get_default_branch(target_repo_full_name)

        # Build file map with merge for root-level files only.
        # Per-folder CLAUDE.md and rule files are fully generated — no merge needed.
        repo_name = target_repo_full_name.split("/")[-1] if "/" in target_repo_full_name else target_repo_full_name
        # Only these root files may have user content that needs merge-preserving
        _MERGE_CANDIDATES = {"CLAUDE.md", "AGENTS.md", ".mcp.json", ".cursor/mcp.json", ".claude/settings.json"}
        files: dict[str, str] = {}
        for path, content in generated.items():
            if path in _MERGE_CANDIDATES:
                existing = push_client.get_file_content(target_repo_full_name, path, default_branch)
                if path == ".claude/settings.json":
                    generated_config = json.loads(content)
                    files[path] = _merge_settings_json(existing, generated_config)
                else:
                    merge_strategy = self._get_merge_strategy(path)
                    if merge_strategy == "markdown":
                        files[path] = _merge_markdown(existing, content, repo_name)
                    elif merge_strategy == "json":
                        generated_config = json.loads(content)
                        files[path] = _merge_json_config(existing, generated_config)
                    else:
                        files[path] = content
            else:
                files[path] = content
        delivered_paths = list(files.keys())
        executable_paths = {p for p in files if p.endswith(".sh")}

        if strategy == "pr":
            branch_name = f"{branch_prefix}/sync-architecture-outputs"
            push_client.create_branch(target_repo_full_name, branch_name, default_branch)
            push_client.commit_files(
                target_repo_full_name,
                branch_name,
                files,
                "chore: sync Archie blueprint outputs",
                executable_paths=executable_paths,
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
                "chore: sync Archie blueprint outputs",
                executable_paths=executable_paths,
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

    async def _apply_local(
        self,
        source_repo_id: str,
        outputs: list[str],
        target_local_path: Optional[str],
    ) -> DeliveryResult:
        """Write outputs directly to a local directory."""
        if not target_local_path:
            raise ValidationError("target_local_path is required for local strategy.")

        generated = await self.preview(source_repo_id, outputs)
        local_client = LocalPushClient(target_local_path)

        # Merge root-level files that may have user content
        _MERGE_CANDIDATES = {"CLAUDE.md", "AGENTS.md", ".mcp.json", ".cursor/mcp.json", ".claude/settings.json"}
        repo_name = target_local_path.rstrip("/").split("/")[-1]
        files: dict[str, str] = {}
        for path, content in generated.items():
            if path in _MERGE_CANDIDATES:
                existing = local_client.get_file_content(path)
                if path == ".claude/settings.json":
                    generated_config = json.loads(content)
                    files[path] = _merge_settings_json(existing, generated_config)
                else:
                    merge_strategy = self._get_merge_strategy(path)
                    if merge_strategy == "markdown":
                        files[path] = _merge_markdown(existing, content, repo_name)
                    elif merge_strategy == "json":
                        generated_config = json.loads(content)
                        files[path] = _merge_json_config(existing, generated_config)
                    else:
                        files[path] = content
            else:
                files[path] = content

        executable_paths = {p for p in files if p.endswith(".sh")}
        written = local_client.write_files(files, executable_paths=executable_paths)
        return DeliveryResult(
            status="success",
            strategy="local",
            files_delivered=written,
        )

    async def _load_intent_layer_files(self, repo_id: str) -> dict[str, str]:
        """Load pre-generated intent layer files from storage."""
        il_base = f"blueprints/{repo_id}/intent_layer"
        try:
            if not await self._storage.exists(il_base + "/CLAUDE.md"):
                return {}
            raw_paths = await self._storage.list_files(il_base)
            prefix = il_base + "/"
            files: dict[str, str] = {}
            for file_path in raw_paths:
                rel_path = file_path[len(prefix):] if file_path.startswith(prefix) else file_path
                if not rel_path:
                    continue
                content = await self._storage.read(file_path)
                text = content.decode("utf-8") if isinstance(content, bytes) else content
                files[rel_path] = text
            return files
        except Exception:
            return {}

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

    @staticmethod
    def _should_include(path: str, outputs: list[str]) -> bool:
        """Check if a file path should be included based on requested outputs."""
        if path == "CLAUDE.md":
            return "claude_md" in outputs
        if path == "AGENTS.md":
            return "agents_md" in outputs
        if path == "CODEBASE_MAP.md":
            return "codebase_map" in outputs
        if path.startswith(".claude/rules/"):
            return "claude_rules" in outputs
        if path.startswith(".cursor/rules/"):
            return "cursor_rules" in outputs
        if path.endswith("/CLAUDE.md"):
            return "intent_layer" in outputs
        return False

    @staticmethod
    def _build_pr_body(files: list[str], source_repo_id: str) -> str:
        file_list = "\n".join(f"- `{f}`" for f in files)
        return (
            "## Architecture Outputs\n\n"
            f"Auto-generated from blueprint analysis (source: `{source_repo_id}`).\n\n"
            f"### Files\n{file_list}\n\n"
            "---\n"
            "Generated by [Archie](https://github.com/your-org/archie)"
        )
