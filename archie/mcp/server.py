"""Standalone MCP server that reads from .archie/blueprint.json.

No database required — all data comes from local files produced by `archie init`.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Blueprint loading helpers
# ---------------------------------------------------------------------------

def _load_blueprint(project_root: Path) -> dict[str, Any] | None:
    """Load the structured blueprint JSON from .archie/blueprint.json."""
    bp_file = project_root / ".archie" / "blueprint.json"
    if not bp_file.exists():
        return None
    try:
        return json.loads(bp_file.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tool logic functions (testable without MCP protocol)
# ---------------------------------------------------------------------------

def where_to_put(blueprint: dict[str, Any], component_type: str) -> str:
    """Find the correct location for a new component.

    Reads from blueprint.architecture_rules.file_placement_rules and
    blueprint.quick_reference.where_to_put_code.
    """
    type_lower = component_type.lower().strip()
    matches: list[dict] = []

    # Search file placement rules
    rules = blueprint.get("architecture_rules", {})
    for fp in rules.get("file_placement_rules", []):
        if type_lower in fp.get("component_type", "").lower():
            matches.append({
                "source": "file_placement_rule",
                "component_type": fp.get("component_type", ""),
                "location": fp.get("location", ""),
                "naming_pattern": fp.get("naming_pattern", ""),
                "example": fp.get("example", ""),
                "description": fp.get("description", ""),
            })

    # Search quick_reference.where_to_put_code
    qr = blueprint.get("quick_reference", {})
    for key, loc in qr.get("where_to_put_code", {}).items():
        if type_lower in key.lower():
            matches.append({
                "source": "quick_reference",
                "component_type": key,
                "location": loc,
            })

    if not matches:
        available = set()
        for fp in rules.get("file_placement_rules", []):
            available.add(fp.get("component_type", ""))
        for key in qr.get("where_to_put_code", {}):
            available.add(key)
        return (
            f"No placement rule found for '{component_type}'.\n"
            f"Available component types: {', '.join(sorted(available))}"
        )

    lines = [f"# Where to put: {component_type}\n"]
    for m in matches:
        lines.append(f"**Location:** `{m['location']}`")
        if m.get("naming_pattern"):
            lines.append(f"**Naming pattern:** `{m['naming_pattern']}`")
        if m.get("example"):
            lines.append(f"**Example:** `{m['example']}`")
        if m.get("description"):
            lines.append(f"**Description:** {m['description']}")
        lines.append("")

    return "\n".join(lines)


def check_naming(blueprint: dict[str, Any], scope: str, name: str) -> str:
    """Validate a proposed name against naming conventions.

    Reads from blueprint.architecture_rules.naming_conventions.
    """
    scope_lower = scope.lower().strip()
    matches: list[dict] = []
    violations: list[dict] = []

    conventions = blueprint.get("architecture_rules", {}).get("naming_conventions", [])

    for nc in conventions:
        if scope_lower not in nc.get("scope", "").lower():
            continue

        pattern = nc.get("pattern", "")
        entry = {
            "scope": nc.get("scope", ""),
            "pattern": pattern,
            "description": nc.get("description", ""),
            "examples": nc.get("examples", []),
        }

        try:
            if pattern.startswith("^") or pattern.endswith("$"):
                if re.match(pattern, name):
                    matches.append(entry)
                else:
                    violations.append(entry)
            else:
                entry["note"] = "Convention pattern is not a regex; verify manually."
                matches.append(entry)
        except re.error:
            entry["note"] = "Pattern could not be parsed as regex."
            matches.append(entry)

    result = {
        "name": name,
        "scope": scope,
        "is_valid": len(violations) == 0,
        "matching_conventions": matches,
        "violations": violations,
    }

    if violations:
        lines = [f"**NAMING ISSUE** -- `{name}` does not match convention for {scope}.\n"]
        for v in violations:
            lines.append(f"- Expected: {v['pattern']} ({v['description']})")
            if v["examples"]:
                lines.append(f"  Examples: {', '.join(f'`{e}`' for e in v['examples'][:3])}")
        lines.append(f"\n```json\n{json.dumps(result, indent=2)}\n```")
        return "\n".join(lines)

    if matches:
        lines = [f"**OK** -- `{name}` follows naming convention for {scope}.\n"]
        for m in matches:
            lines.append(f"- Convention: {m['pattern']} ({m['description']})")
        lines.append(f"\n```json\n{json.dumps(result, indent=2)}\n```")
        return "\n".join(lines)

    available_scopes = set(nc.get("scope", "") for nc in conventions)
    return (
        f"No naming convention found for scope '{scope}'.\n"
        f"Available scopes: {', '.join(sorted(available_scopes))}"
    )


def get_architecture_rules(blueprint: dict[str, Any]) -> str:
    """Return all architecture rules as formatted text."""
    rules = blueprint.get("architecture_rules", {})
    lines = ["# Architecture Rules\n"]

    placement = rules.get("file_placement_rules", [])
    if placement:
        lines.append("## File Placement Rules\n")
        for fp in placement:
            lines.append(f"### {fp.get('component_type', 'Unknown')}")
            lines.append(f"- **Location:** `{fp.get('location', '')}`")
            if fp.get("naming_pattern"):
                lines.append(f"- **Naming pattern:** `{fp['naming_pattern']}`")
            if fp.get("example"):
                lines.append(f"- **Example:** `{fp['example']}`")
            if fp.get("description"):
                lines.append(f"- **Description:** {fp['description']}")
            lines.append("")

    conventions = rules.get("naming_conventions", [])
    if conventions:
        lines.append("## Naming Conventions\n")
        for nc in conventions:
            lines.append(f"### {nc.get('scope', 'Unknown')}")
            lines.append(f"- **Pattern:** `{nc.get('pattern', '')}`")
            if nc.get("description"):
                lines.append(f"- **Description:** {nc['description']}")
            if nc.get("examples"):
                lines.append(f"- **Examples:** {', '.join(f'`{e}`' for e in nc['examples'][:5])}")
            lines.append("")

    if len(lines) == 1:
        return "No architecture rules found in blueprint."

    return "\n".join(lines)


def get_component_info(blueprint: dict[str, Any], component_name: str) -> str:
    """Return details for a specific component by name."""
    name_lower = component_name.lower().strip()
    components = blueprint.get("components", {}).get("components", [])

    for comp in components:
        if name_lower in comp.get("name", "").lower():
            lines = [f"# Component: {comp.get('name', '')}\n"]
            if comp.get("location"):
                lines.append(f"**Location:** `{comp['location']}`")
            if comp.get("responsibility"):
                lines.append(f"**Responsibility:** {comp['responsibility']}")
            if comp.get("platform"):
                lines.append(f"**Platform:** {comp['platform']}")
            if comp.get("depends_on"):
                lines.append(f"**Depends on:** {', '.join(comp['depends_on'])}")
            if comp.get("exposes_to"):
                lines.append(f"**Exposes to:** {', '.join(comp['exposes_to'])}")
            if comp.get("key_files"):
                lines.append("\n**Key files:**")
                for kf in comp["key_files"]:
                    if isinstance(kf, dict):
                        path = kf.get("path", kf.get("file", ""))
                        purpose = kf.get("purpose", kf.get("description", ""))
                        lines.append(f"- `{path}` -- {purpose}")
                    else:
                        lines.append(f"- `{kf}`")
            if comp.get("key_interfaces"):
                lines.append("\n**Key interfaces:**")
                for ki in comp["key_interfaces"]:
                    iname = ki.get("name", "")
                    desc = ki.get("description", "")
                    lines.append(f"- **{iname}**: {desc}")
            return "\n".join(lines)

    available = [c.get("name", "") for c in components if c.get("name")]
    return (
        f"Component '{component_name}' not found.\n"
        f"Available components: {', '.join(available)}"
    )


def list_components(blueprint: dict[str, Any]) -> str:
    """List all components with their paths and purposes."""
    components = blueprint.get("components", {}).get("components", [])

    if not components:
        return "No components found in blueprint."

    lines = ["# Components\n"]
    lines.append("| Name | Location | Responsibility |")
    lines.append("|------|----------|----------------|")
    for comp in components:
        name = comp.get("name", "")
        location = comp.get("location", "")
        resp = comp.get("responsibility", "")
        lines.append(f"| **{name}** | `{location}` | {resp} |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP server setup
# ---------------------------------------------------------------------------

NO_BLUEPRINT_MSG = (
    "No blueprint found. Run `archie init` in the project directory first "
    "to generate .archie/blueprint.json."
)


def _create_server(project_root: Path):
    """Create and configure the standalone MCP server."""
    from mcp.server import Server
    from mcp.types import Tool, TextContent

    try:
        srv = Server("archie-local")
    except TypeError:
        srv = Server()
        srv.name = "archie-local"

    @srv.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return [
            Tool(
                name="where_to_put",
                description=(
                    "REQUIRED before creating new files. Returns the correct directory, "
                    "naming pattern, and example for a given component type."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_type": {
                            "type": "string",
                            "description": "Type of component (e.g. 'service', 'controller', 'entity')",
                        }
                    },
                    "required": ["component_type"],
                },
            ),
            Tool(
                name="check_naming",
                description=(
                    "Validates a proposed name against the project's naming conventions."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scope": {
                            "type": "string",
                            "description": "Scope (e.g. 'classes', 'functions', 'files')",
                        },
                        "name": {
                            "type": "string",
                            "description": "The name to check (e.g. 'UserService')",
                        },
                    },
                    "required": ["scope", "name"],
                },
            ),
            Tool(
                name="get_architecture_rules",
                description="Returns all architecture rules (file placement and naming conventions).",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_component_info",
                description="Returns details for a specific component by name.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_name": {
                            "type": "string",
                            "description": "Name of the component to look up",
                        }
                    },
                    "required": ["component_name"],
                },
            ),
            Tool(
                name="list_components",
                description="Lists all architectural components with their paths and purposes.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @srv.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
        bp = _load_blueprint(project_root)
        if bp is None:
            return [TextContent(type="text", text=NO_BLUEPRINT_MSG)]

        if name == "where_to_put":
            result = where_to_put(bp, arguments["component_type"])
        elif name == "check_naming":
            result = check_naming(bp, arguments["scope"], arguments["name"])
        elif name == "get_architecture_rules":
            result = get_architecture_rules(bp)
        elif name == "get_component_info":
            result = get_component_info(bp, arguments["component_name"])
        elif name == "list_components":
            result = list_components(bp)
        else:
            result = f"Unknown tool: {name}"

        return [TextContent(type="text", text=result)]

    return srv


def run_mcp_server(project_root: Path) -> None:
    """Start the standalone MCP server over stdio."""
    import asyncio
    from mcp.server.stdio import stdio_server

    srv = _create_server(project_root)

    async def _run():
        try:
            async with stdio_server() as (read_stream, write_stream):
                print(
                    f"Archie MCP server running for {project_root}",
                    file=sys.stderr,
                    flush=True,
                )
                await srv.run(
                    read_stream,
                    write_stream,
                    srv.create_initialization_options(),
                )
        except KeyboardInterrupt:
            print("\nServer stopped by user", file=sys.stderr)
        except Exception as e:
            print(f"\nServer error: {e}", file=sys.stderr)
            sys.exit(1)

    asyncio.run(_run())
