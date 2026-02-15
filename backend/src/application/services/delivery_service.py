"""Delivery service -- push architecture outputs to a target GitHub repository."""
import json
from dataclasses import dataclass
from typing import Optional

from domain.entities.blueprint import StructuredBlueprint
from domain.exceptions.domain_exceptions import ValidationError
from application.services.agent_file_generator import (
    generate_claude_md,
    generate_cursor_rules,
    generate_agents_md,
)
from infrastructure.external.github_push_client import GitHubPushClient


# Output key → file path in target repo
OUTPUT_FILE_MAP: dict[str, str] = {
    "claude_md": "CLAUDE.md",
    "agents_md": "AGENTS.md",
    "cursor_rules": ".cursor/rules/architecture.md",
    "mcp_claude": ".mcp.json",
    "mcp_cursor": ".cursor/mcp.json",
}

VALID_OUTPUTS = set(OUTPUT_FILE_MAP.keys())

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

        # Build file map: output key → target file path → content
        files: dict[str, str] = {}
        for key, content in generated.items():
            files[OUTPUT_FILE_MAP[key]] = content

        push_client = GitHubPushClient(token)
        default_branch = push_client.get_default_branch(target_repo_full_name)
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

    def _generate_outputs(
        self,
        blueprint: StructuredBlueprint,
        outputs: list[str],
    ) -> dict[str, str]:
        """Generate selected output files from a blueprint."""
        generators = {
            "claude_md": generate_claude_md,
            "cursor_rules": generate_cursor_rules,
            "agents_md": generate_agents_md,
            "mcp_claude": _generate_mcp_config,
            "mcp_cursor": _generate_mcp_config,
        }
        result: dict[str, str] = {}
        for key in outputs:
            if key not in generators:
                raise ValidationError(f"Unknown output type: {key}. Valid: {VALID_OUTPUTS}")
            result[key] = generators[key](blueprint)
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
