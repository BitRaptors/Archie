"""Renderer adapter — bridges archie CLI to existing backend renderers."""
from __future__ import annotations
import sys
from pathlib import Path

# Add backend/src to path so we can import existing renderers
_BACKEND_SRC = str(Path(__file__).resolve().parents[2] / "backend" / "src")
if _BACKEND_SRC not in sys.path:
    sys.path.insert(0, _BACKEND_SRC)


def render_outputs(blueprint_dict: dict, project_root: Path) -> dict[str, str]:
    """Render all output files from a blueprint dict.

    Returns a dict of {relative_path: content} for all generated files.
    Also writes them to disk under project_root.
    """
    from domain.entities.blueprint import StructuredBlueprint
    from application.services.blueprint_renderer import render_blueprint_markdown
    from application.services.agent_file_generator import generate_all

    # Normalize subagent output to match StructuredBlueprint schema
    _normalize_blueprint_dict(blueprint_dict)

    # Parse the dict into a StructuredBlueprint (Pydantic validates/coerces)
    bp = StructuredBlueprint.model_validate(blueprint_dict)

    files: dict[str, str] = {}

    # 1. Full markdown rendering
    markdown = render_blueprint_markdown(bp)
    files["ARCHITECTURE.md"] = markdown

    # 2. Agent files (CLAUDE.md, AGENTS.md, rules)
    output = generate_all(bp)
    files["CLAUDE.md"] = output.claude_md
    files["AGENTS.md"] = output.agents_md
    for rule_file in output.rule_files:
        files[rule_file.claude_path] = rule_file.render_claude()
        files[rule_file.cursor_path] = rule_file.render_cursor()

    # Write all files to disk
    for rel_path, content in files.items():
        full_path = project_root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    return files


def _normalize_blueprint_dict(bp: dict) -> None:
    """Normalize subagent output to match StructuredBlueprint schema in-place."""
    # key_files: list[str] -> list[dict[str, str]]
    for comp in bp.get("components", {}).get("components", []):
        if "key_files" in comp and comp["key_files"]:
            comp["key_files"] = [
                {"path": f, "purpose": ""} if isinstance(f, str) else f
                for f in comp["key_files"]
            ]
    # contracts implementing_files: same normalization
    for contract in bp.get("components", {}).get("contracts", []):
        if "implementing_files" in contract and contract["implementing_files"]:
            if isinstance(contract["implementing_files"][0], str):
                contract["implementing_files"] = [
                    {"path": f} for f in contract["implementing_files"]
                ]
