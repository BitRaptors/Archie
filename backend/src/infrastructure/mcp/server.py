"""MCP server for architecture blueprints."""

import sys
import json
from pathlib import Path
from typing import Optional

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Resource, Tool, TextContent
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
DOCS_DIR = ROOT_DIR / "DOCS"
STORAGE_DIR = ROOT_DIR / "backend" / "storage"

# Initialize managers
resources_manager = BlueprintResources(DOCS_DIR, storage_dir=STORAGE_DIR)
tools_manager = BlueprintTools(DOCS_DIR, storage_dir=STORAGE_DIR)

# ---------------------------------------------------------------------------
# Active repository helper (reads from DB on every call — always fresh)
# ---------------------------------------------------------------------------

_user_profile_repo = None


async def _ensure_user_profile_repo():
    """Lazily create a UserProfileRepository (needs async Supabase client)."""
    global _user_profile_repo
    if _user_profile_repo is not None:
        return

    try:
        from infrastructure.persistence.supabase_client import get_supabase_client_async
        from infrastructure.persistence.supabase_adapter import SupabaseAdapter
        from infrastructure.persistence.user_profile_repository import UserProfileRepository

        client = await get_supabase_client_async()
        db = SupabaseAdapter(client)
        _user_profile_repo = UserProfileRepository(db=db)
    except Exception:
        # If DB is unavailable, repo stays None — tools will report no active repo
        pass


async def _get_active_repo_id() -> Optional[str]:
    """Return the currently-active repository ID, or None."""
    await _ensure_user_profile_repo()
    if _user_profile_repo is None:
        return None
    try:
        profile = await _user_profile_repo.get_default()
        return profile.active_repo_id if profile else None
    except Exception:
        return None


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
        all_resources = await resources_manager.list_resources()
        active_id = await _get_active_repo_id()
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

        # Reject reads for non-active repos
        active_id = await _get_active_repo_id()
        if active_id and "analyzed/" in uri_str:
            # Extract repo_id from URI: blueprint://analyzed/<repo_id>[/...]
            parts = uri_str.replace("blueprint://analyzed/", "").split("/")
            if parts and parts[0] != active_id:
                raise ValueError(
                    f"Resource belongs to a different repository. Active: {active_id}"
                )

        result = resources_manager.get_resource(uri_str)
        if result:
            mime_type, content = result
            return [ReadResourceContents(content=content, mime_type=mime_type)]
        raise ValueError(f"Resource not found: {uri_str}")

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @srv.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            # ── Reference architecture tools (no repo needed) ─────────
            Tool(
                name="get_pattern",
                description="Get detailed information about an architectural pattern by ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pattern_id": {
                            "type": "string",
                            "description": "Pattern identifier (e.g., 'context-hook', 'service-registry')"
                        }
                    },
                    "required": ["pattern_id"]
                }
            ),
            Tool(
                name="list_patterns",
                description="List all available patterns with summaries",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "stack": {
                            "type": "string",
                            "enum": ["backend", "frontend"],
                            "description": "Optional filter by stack"
                        }
                    }
                }
            ),
            Tool(
                name="get_layer_rules",
                description="Get what a specific layer can/cannot do",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "layer": {
                            "type": "string",
                            "enum": ["presentation", "application", "domain", "infrastructure"],
                            "description": "Layer name"
                        }
                    },
                    "required": ["layer"]
                }
            ),
            Tool(
                name="get_principle",
                description="Get a specific principle (e.g., 'SRP', 'colocation')",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "principle_name": {
                            "type": "string",
                            "description": "Principle name or acronym"
                        }
                    },
                    "required": ["principle_name"]
                }
            ),
            # ── Active-repo tools (no repo_id parameter) ─────────────
            Tool(
                name="get_repository_blueprint",
                description="Get the full generated architecture blueprint for the active repository.",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="list_repository_sections",
                description="List all addressable sections in the active repository's blueprint.",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="get_repository_section",
                description="Get a specific section from the active repository's blueprint (token-efficient).",
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
                name="validate_import",
                description="Check if an import is allowed by the architecture rules. Returns violation details if forbidden.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_file": {"type": "string", "description": "File containing the import (e.g. 'src/api/routes/users.py')"},
                        "target_import": {"type": "string", "description": "Module being imported (e.g. 'src/infrastructure/db')"}
                    },
                    "required": ["source_file", "target_import"]
                }
            ),
            Tool(
                name="where_to_put",
                description="Find the correct file location for a new component type (e.g. 'service', 'controller', 'entity').",
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
                description="Check if a name follows the project's naming conventions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scope": {"type": "string", "description": "Scope of the name (e.g. 'classes', 'functions', 'files', 'modules')"},
                        "name": {"type": "string", "description": "The name to check (e.g. 'UserService', 'get_user')"}
                    },
                    "required": ["scope", "name"]
                }
            ),
        ]

    @srv.call_tool()
    async def call_tool(name: str, arguments: dict):
        from mcp.types import TextContent

        # ── Reference tools (no active repo required) ─────────────────
        if name == "get_pattern":
            result = tools_manager.get_pattern(arguments["pattern_id"])
            return [TextContent(type="text", text=result)]

        elif name == "list_patterns":
            result = tools_manager.list_patterns(arguments.get("stack"))
            return [TextContent(type="text", text=result)]

        elif name == "get_layer_rules":
            result = tools_manager.get_layer_rules(arguments["layer"])
            return [TextContent(type="text", text=result)]

        elif name == "get_principle":
            result = tools_manager.get_principle(arguments["principle_name"])
            return [TextContent(type="text", text=result)]

        # ── Active-repo tools ─────────────────────────────────────────
        repo_id = await _get_active_repo_id()
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

        elif name == "validate_import":
            result = tools_manager.validate_import(
                repo_id, arguments["source_file"], arguments["target_import"]
            )
            return [TextContent(type="text", text=result)]

        elif name == "where_to_put":
            result = tools_manager.where_to_put(repo_id, arguments["component_type"])
            return [TextContent(type="text", text=result)]

        elif name == "check_naming":
            result = tools_manager.check_naming(
                repo_id, arguments["scope"], arguments["name"]
            )
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
