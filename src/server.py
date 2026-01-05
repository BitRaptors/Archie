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

# Determine docs directory (relative to this file)
DOCS_DIR = Path(__file__).parent.parent / "DOCS"

# Initialize server
try:
    server = Server("architecture-blueprints")
except TypeError:
    # Fallback for different Server initialization
    server = Server()
    server.name = "architecture-blueprints"

# Initialize managers
resources_manager = BlueprintResources(DOCS_DIR)
tools_manager = BlueprintTools(DOCS_DIR)


@server.list_resources()
async def list_resources() -> list[Resource]:
    """List all available blueprint resources."""
    return resources_manager.list_resources()


@server.read_resource()
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


# Query Tools
@server.list_tools()
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
        # Validation Tools
        Tool(
            name="check_layer_violation",
            description="Check if code violates layer boundaries",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to check"
                    },
                    "layer": {
                        "type": "string",
                        "enum": ["presentation", "application", "domain", "infrastructure"],
                        "description": "Layer name"
                    }
                },
                "required": ["code", "layer"]
            }
        ),
        Tool(
            name="check_file_placement",
            description="Validate file path follows structure conventions",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path to check"
                    },
                    "stack": {
                        "type": "string",
                        "enum": ["backend", "frontend"],
                        "description": "Stack (backend or frontend)"
                    }
                },
                "required": ["file_path", "stack"]
            }
        ),
        Tool(
            name="suggest_pattern",
            description="Suggest appropriate pattern for a given use case",
            inputSchema={
                "type": "object",
                "properties": {
                    "use_case": {
                        "type": "string",
                        "description": "Description of the use case"
                    },
                    "stack": {
                        "type": "string",
                        "enum": ["backend", "frontend"],
                        "description": "Stack (backend or frontend)"
                    }
                },
                "required": ["use_case", "stack"]
            }
        ),
        Tool(
            name="review_component",
            description="Review code for architectural compliance",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to review"
                    },
                    "component_type": {
                        "type": "string",
                        "description": "Type of component (e.g., 'service', 'hook', 'controller')"
                    },
                    "stack": {
                        "type": "string",
                        "enum": ["backend", "frontend"],
                        "description": "Stack (backend or frontend)"
                    }
                },
                "required": ["code", "component_type", "stack"]
            }
        ),
    ]


@server.call_tool()
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
    
    elif name == "check_layer_violation":
        result = tools_manager.check_layer_violation(
            arguments["code"],
            arguments["layer"]
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "check_file_placement":
        result = tools_manager.check_file_placement(
            arguments["file_path"],
            arguments["stack"]
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "suggest_pattern":
        result = tools_manager.suggest_pattern(
            arguments["use_case"],
            arguments["stack"]
        )
        return [TextContent(type="text", text=result)]
    
    elif name == "review_component":
        result = tools_manager.review_component(
            arguments["code"],
            arguments["component_type"],
            arguments["stack"]
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


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

