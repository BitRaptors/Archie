"""MCP server for architecture blueprints.

All tools operate on the structured JSON blueprint — the single source of truth.
No static markdown reference files are used.
"""

import sys
from pathlib import Path
from typing import Optional

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Resource, Tool
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
        Server = FastMCP
    except ImportError:
        raise ImportError("Please install the mcp package: pip install mcp")

from .resources import BlueprintResources
from .tools import BlueprintTools

# Determine directories (relative to this file)
ROOT_DIR = Path(__file__).parent.parent.parent.parent.parent.absolute()
STORAGE_DIR = ROOT_DIR / "backend" / "storage"

# Initialize managers
resources_manager = BlueprintResources(storage_dir=STORAGE_DIR)
tools_manager = BlueprintTools(storage_dir=STORAGE_DIR)

# ---------------------------------------------------------------------------
# Active repository helper
# ---------------------------------------------------------------------------

_user_profile_repo = None

# Last-known active repo — compared on each request to detect changes.
_last_active_repo_id: Optional[str] = None


async def _ensure_user_profile_repo():
    """Lazily create a UserProfileRepository (needs async DB client)."""
    global _user_profile_repo
    if _user_profile_repo is not None:
        return

    try:
        from infrastructure.persistence.db_factory import create_db
        from infrastructure.persistence.user_profile_repository import UserProfileRepository

        db = await create_db()
        _user_profile_repo = UserProfileRepository(db=db)
    except Exception as exc:
        print(
            f"⚠ MCP: Failed to initialise UserProfileRepository: {exc}",
            file=sys.stderr,
        )


async def _get_active_repo_id() -> Optional[str]:
    """Return the currently-active repository ID, or None."""
    await _ensure_user_profile_repo()
    if _user_profile_repo is None:
        return None
    try:
        profile = await _user_profile_repo.get_default()
        return profile.active_repo_id if profile else None
    except Exception as exc:
        print(f"⚠ MCP: Failed to query active repo: {exc}", file=sys.stderr)
        return None


async def _notify_if_repo_changed(srv: Server, current_id: Optional[str]):
    """Send ``resources/list_changed`` if the active repo changed since last check.

    Called inline from request handlers — no background tasks required.
    """
    global _last_active_repo_id
    if current_id == _last_active_repo_id:
        return
    old = _last_active_repo_id
    _last_active_repo_id = current_id
    print(f"✓ MCP: Active repo changed: {old} → {current_id}", file=sys.stderr)
    try:
        session = srv.request_context.session
        await session.send_resource_list_changed()
        print("✓ MCP: Sent resources/list_changed notification", file=sys.stderr)
    except Exception as exc:
        print(f"⚠ MCP: Could not send list_changed: {exc}", file=sys.stderr)


NO_ACTIVE_REPO_MSG = (
    "No active repository is set. "
    "Please select an active repository via the Workspace UI first."
)


def create_server():
    """Create and configure the MCP server instance."""
    try:
        srv = Server("architecture-blueprints")
    except TypeError:
        srv = Server()
        srv.name = "architecture-blueprints"

    # ------------------------------------------------------------------
    # Resources — filtered to active repo
    # ------------------------------------------------------------------

    @srv.list_resources()
    async def list_resources() -> list[Resource]:
        global _last_active_repo_id
        all_resources = await resources_manager.list_resources()
        active_id = await _get_active_repo_id()
        _last_active_repo_id = active_id  # seed baseline for change detection
        if not active_id:
            return all_resources  # show everything when nothing is active
        # Only expose resources belonging to the active repo
        return [
            r for r in all_resources
            if active_id in str(r.uri)
        ]

    @srv.read_resource()
    async def read_resource(uri):
        from mcp.server.lowlevel.helper_types import ReadResourceContents
        uri_str = str(uri)

        # Always resolve to the active repo so stale cached URIs
        # (containing an old repo UUID) still serve current data.
        if uri_str.startswith("blueprint://analyzed/"):
            active_id = await _get_active_repo_id()
            await _notify_if_repo_changed(srv, active_id)
            if active_id:
                path_parts = uri_str.replace("blueprint://analyzed/", "").split("/")
                if path_parts:
                    path_parts[0] = active_id
                    uri_str = "blueprint://analyzed/" + "/".join(path_parts)

        result = resources_manager.get_resource(uri_str)
        if result:
            mime_type, content = result
            return [ReadResourceContents(content=content, mime_type=mime_type)]
        raise ValueError(f"Resource not found: {uri_str}")

    # ------------------------------------------------------------------
    # Tools — all operate on the active repository's blueprint JSON
    # ------------------------------------------------------------------

    @srv.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="get_repository_blueprint",
                description=(
                    "Get the full architecture blueprint for the active repository. "
                    "Contains component boundaries, file placement rules, "
                    "and naming conventions. Use list_repository_sections + get_repository_section "
                    "for token-efficient partial reads."
                ),
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="list_repository_sections",
                description="List all addressable section IDs in the active repository's blueprint. Use with get_repository_section to fetch specific sections.",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="get_repository_section",
                description="Get a specific section from the active repository's blueprint by slug. Token-efficient alternative to reading the full blueprint.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "section_id": {
                            "type": "string",
                            "description": "Section slug (e.g., 'layer-architecture')"
                        }
                    },
                    "required": ["section_id"]
                }
            ),
            Tool(
                name="where_to_put",
                description=(
                    "REQUIRED before creating new files. Returns the correct directory, naming pattern, "
                    "and example for a given component type. Call this to determine where new services, "
                    "controllers, entities, repositories, etc. should be placed."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_type": {"type": "string", "description": "Type of component (e.g. 'service', 'controller', 'entity', 'repository')"}
                    },
                    "required": ["component_type"]
                }
            ),
            Tool(
                name="check_naming",
                description=(
                    "Validates a proposed name against the project's naming conventions. "
                    "Call this before naming new classes, functions, or files to ensure consistency."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scope": {"type": "string", "description": "Scope of the name (e.g. 'classes', 'functions', 'files', 'modules')"},
                        "name": {"type": "string", "description": "The name to check (e.g. 'UserService', 'get_user')"}
                    },
                    "required": ["scope", "name"]
                }
            ),
            Tool(
                name="how_to_implement",
                description=(
                    "Look up how a capability or feature is already implemented in this codebase. "
                    "Returns recommended libraries, patterns, key files, and usage examples. "
                    "Call this before implementing features like push notifications, maps, auth, etc."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "feature": {
                            "type": "string",
                            "description": "The feature or capability (e.g. 'push notifications', 'maps', 'authentication', 'image loading')"
                        }
                    },
                    "required": ["feature"]
                }
            ),
        ]

    @srv.call_tool()
    async def call_tool(name: str, arguments: dict):
        from mcp.types import TextContent

        # All tools require an active repo
        repo_id = await _get_active_repo_id()
        await _notify_if_repo_changed(srv, repo_id)
        if not repo_id:
            return [TextContent(type="text", text=NO_ACTIVE_REPO_MSG)]

        if name == "get_repository_blueprint":
            result = tools_manager.get_repository_blueprint(repo_id)
            return [TextContent(type="text", text=result)]

        elif name == "list_repository_sections":
            result = tools_manager.list_repository_sections(repo_id)
            return [TextContent(type="text", text=result)]

        elif name == "get_repository_section":
            result = tools_manager.get_repository_section(repo_id, arguments["section_id"])
            return [TextContent(type="text", text=result)]

        elif name == "where_to_put":
            result = tools_manager.where_to_put(repo_id, arguments["component_type"])
            return [TextContent(type="text", text=result)]

        elif name == "check_naming":
            result = tools_manager.check_naming(
                repo_id, arguments["scope"], arguments["name"]
            )
            return [TextContent(type="text", text=result)]

        elif name == "how_to_implement":
            result = tools_manager.how_to_implement(repo_id, arguments["feature"])
            return [TextContent(type="text", text=result)]

        else:
            raise ValueError(f"Unknown tool: {name}")

    return srv


server = create_server()


async def main():
    """Run the MCP server."""
    try:
        async with stdio_server() as (read_stream, write_stream):
            print("\n✓ MCP server is running and ready for connections", file=sys.stderr, flush=True)
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except KeyboardInterrupt:
        print("\n✓ Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"\n✗ Server error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
