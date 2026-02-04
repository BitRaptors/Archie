"""MCP server for architecture blueprints."""

import sys
import json
from pathlib import Path
from typing import Literal, Optional, Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Resource, Tool, TextContent
except ImportError:
    # Fallback for different MCP SDK versions
    try:
        from mcp.server.fastmcp import FastMCP
        Server = FastMCP
    except ImportError:
        raise ImportError("Please install the mcp package: pip install mcp")

from .resources import BlueprintResources
from .tools import BlueprintTools

# Determine directories (relative to this file)
# backend/src/infrastructure/mcp/server.py -> parent x 4 is backend/ -> parent x 5 is root
ROOT_DIR = Path(__file__).parent.parent.parent.parent.parent.absolute()
DOCS_DIR = ROOT_DIR / "DOCS"
STORAGE_DIR = ROOT_DIR / "backend" / "storage"

# Initialize server
try:
    server = Server("architecture-blueprints")
except TypeError:
    # Fallback for different Server initialization
    server = Server()
    server.name = "architecture-blueprints"

# Initialize managers (repository_repository will be initialized lazily if DB is available)
resources_manager = BlueprintResources(DOCS_DIR, storage_dir=STORAGE_DIR)
tools_manager = BlueprintTools(DOCS_DIR, storage_dir=STORAGE_DIR)


def create_server():
    """Create and configure the MCP server instance."""
    try:
        srv = Server("architecture-blueprints")
    except TypeError:
        # Fallback for different Server initialization
        srv = Server()
        srv.name = "architecture-blueprints"

    @srv.list_resources()
    async def list_resources() -> list[Resource]:
        """List all available blueprint resources."""
        return await resources_manager.list_resources()

    @srv.read_resource()
    async def read_resource(uri):
        """Read a blueprint resource."""
        from mcp.types import TextResourceContents
        
        # Convert AnyUrl to string if needed
        uri_str = str(uri)
        
        result = resources_manager.get_resource(uri_str)
        if result:
            mime_type, content = result
            return TextResourceContents(
                uri=uri_str,
                text=content,
                mimeType=mime_type
            )
        raise ValueError(f"Resource not found: {uri_str}")

    @srv.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available tools."""
        return [
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
            # Analyzed Repository Tools
            Tool(
                name="list_analyzed_repositories",
                description="List all analyzed repositories",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="get_repository_blueprint",
                description="Get the full generated backend architecture blueprint for a repository",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_id": {"type": "string", "description": "Repository ID (e.g., UUID from storage)"}
                    },
                    "required": ["repo_id"]
                }
            ),
            Tool(
                name="list_repository_sections",
                description="List all addressable sections (slugs) in a repository's blueprint",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_id": {"type": "string", "description": "Repository ID"}
                    },
                    "required": ["repo_id"]
                }
            ),
            Tool(
                name="get_repository_section",
                description="Get a specific section from a repository's blueprint (token-efficient)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_id": {"type": "string", "description": "Repository ID"},
                        "section_id": {"type": "string", "description": "Section slug (e.g., 'layer-architecture')"}
                    },
                    "required": ["repo_id", "section_id"]
                }
            ),
        ]

    @srv.call_tool()
    async def call_tool(name: str, arguments: dict):
        """Handle tool calls."""
        from mcp.types import TextContent
        
        if name == "get_pattern":
            result = tools_manager.get_pattern(arguments["pattern_id"])
            return [TextContent(type="text", text=result)]
        
        elif name == "list_patterns":
            stack = arguments.get("stack")
            result = tools_manager.list_patterns(stack)
            return [TextContent(type="text", text=result)]
        
        elif name == "get_layer_rules":
            result = tools_manager.get_layer_rules(arguments["layer"])
            return [TextContent(type="text", text=result)]
        
        elif name == "get_principle":
            result = tools_manager.get_principle(arguments["principle_name"])
            return [TextContent(type="text", text=result)]
        
        # Analyzed Repository Tools
        elif name == "list_analyzed_repositories":
            result = tools_manager.list_analyzed_repositories()
            return [TextContent(type="text", text=result)]
        
        elif name == "get_repository_blueprint":
            result = tools_manager.get_repository_blueprint(arguments["repo_id"])
            return [TextContent(type="text", text=result)]
        
        elif name == "list_repository_sections":
            result = tools_manager.list_repository_sections(arguments["repo_id"])
            return [TextContent(type="text", text=result)]
            
        elif name == "get_repository_section":
            result = tools_manager.get_repository_section(arguments["repo_id"], arguments["section_id"])
            return [TextContent(type="text", text=result)]
        
        else:
            raise ValueError(f"Unknown tool: {name}")

    return srv


server = create_server()


async def main():
    """Run the MCP server."""
    try:
        # Note: Server is ready when stdio_server context is entered
        async with stdio_server() as (read_stream, write_stream):
            # Server is now running and ready for connections
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

