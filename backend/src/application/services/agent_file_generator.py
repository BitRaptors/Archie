"""Generate agent instruction files (CLAUDE.md, Cursor rules) from structured blueprint JSON.

All outputs derive from the same StructuredBlueprint, ensuring consistency
across CLAUDE.md, Cursor rules, MCP tools, and the human-readable markdown.
"""
from __future__ import annotations

from datetime import datetime, timezone

from domain.entities.blueprint import StructuredBlueprint


def generate_claude_md(blueprint: StructuredBlueprint) -> str:
    """Generate CLAUDE.md from structured blueprint data.

    CLAUDE.md is placed in the project root so AI coding assistants
    (Claude Code, ChatGPT, Copilot, etc.) read it automatically.
    It focuses on actionable rules and quick-reference tables.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    repo = blueprint.meta.repository or "Unknown Repository"
    style = blueprint.meta.architecture_style or "Not determined"

    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────
    lines.append("# CLAUDE.md")
    lines.append("")
    lines.append(f"> Architecture guidance for **{repo}**")
    lines.append(f"> Style: {style}")
    lines.append(f"> Generated: {timestamp}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Executive Summary ──────────────────────────────────────────────
    if blueprint.meta.executive_summary:
        lines.append("## Overview")
        lines.append("")
        lines.append(blueprint.meta.executive_summary)
        lines.append("")

    # ── Architecture Overview ─────────────────────────────────────────
    ad = blueprint.decisions.architectural_style
    if ad.chosen:
        lines.append("## Architecture Overview")
        lines.append("")
        lines.append(f"**Style:** {ad.chosen}")
        lines.append("")
        if ad.rationale:
            lines.append(ad.rationale)
            lines.append("")

    # ── File Placement ────────────────────────────────────────────────
    if blueprint.architecture_rules.file_placement_rules:
        lines.append("## File Placement")
        lines.append("")
        lines.append("| Component Type | Location | Naming | Example |")
        lines.append("|---------------|----------|--------|---------|")
        for fp in blueprint.architecture_rules.file_placement_rules:
            lines.append(
                f"| {fp.component_type} | `{fp.location}` | `{fp.naming_pattern}` | `{fp.example}` |"
            )
        lines.append("")

    # ── Where to Put Code (quick reference) ───────────────────────────
    if blueprint.quick_reference.where_to_put_code:
        lines.append("## Where to Put Code")
        lines.append("")
        for comp_type, loc in blueprint.quick_reference.where_to_put_code.items():
            lines.append(f"- **{comp_type}** → `{loc}`")
        lines.append("")

    # ── Naming Conventions ────────────────────────────────────────────
    if blueprint.architecture_rules.naming_conventions:
        lines.append("## Naming Conventions")
        lines.append("")
        for nc in blueprint.architecture_rules.naming_conventions:
            examples = ", ".join(f"`{e}`" for e in nc.examples[:4])
            lines.append(f"- **{nc.scope}**: {nc.pattern} (e.g. {examples})")
        lines.append("")

    # ── Communication Patterns ────────────────────────────────────────
    if blueprint.communication.pattern_selection_guide:
        lines.append("## Pattern Selection")
        lines.append("")
        lines.append("| Scenario | Pattern | Rationale |")
        lines.append("|----------|---------|-----------|")
        for psg in blueprint.communication.pattern_selection_guide:
            lines.append(f"| {psg.scenario} | {psg.pattern} | {psg.rationale} |")
        lines.append("")

    # ── Quick Reference: Pattern Selection ─────────────────────────────
    if blueprint.quick_reference.pattern_selection:
        lines.append("## Quick Pattern Lookup")
        lines.append("")
        for scenario, pattern in blueprint.quick_reference.pattern_selection.items():
            lines.append(f"- **{scenario}** → {pattern}")
        lines.append("")

    # ── Developer Recipes ─────────────────────────────────────────────
    if blueprint.developer_recipes:
        lines.append("## Developer Recipes")
        lines.append("")
        for recipe in blueprint.developer_recipes:
            if not recipe.task:
                continue
            lines.append(f"### {recipe.task}")
            if recipe.files:
                lines.append(f"Files: {', '.join(f'`{f}`' for f in recipe.files)}")
            if recipe.steps:
                for i, step in enumerate(recipe.steps, 1):
                    lines.append(f"{i}. {step}")
            lines.append("")

    # ── Implementation Guidelines ──────────────────────────────────────
    if blueprint.implementation_guidelines:
        lines.append("## Implementation Guidelines")
        lines.append("")
        for gl in blueprint.implementation_guidelines:
            if not gl.capability:
                continue
            cat_tag = f" [{gl.category}]" if gl.category else ""
            lines.append(f"### {gl.capability}{cat_tag}")
            if gl.libraries:
                lines.append(f"Libraries: {', '.join(f'`{lib}`' for lib in gl.libraries)}")
            if gl.pattern_description:
                lines.append(f"Pattern: {gl.pattern_description}")
            if gl.key_files:
                lines.append(f"Key files: {', '.join(f'`{f}`' for f in gl.key_files)}")
            if gl.usage_example:
                lines.append(f"Example: `{gl.usage_example}`")
            if gl.tips:
                for tip in gl.tips:
                    lines.append(f"- {tip}")
            lines.append("")

    # ── Pitfalls ──────────────────────────────────────────────────────
    if blueprint.pitfalls:
        lines.append("## Pitfalls")
        lines.append("")
        for pitfall in blueprint.pitfalls:
            if not pitfall.area and not pitfall.description:
                continue
            area_label = f"**{pitfall.area}:** " if pitfall.area else ""
            lines.append(f"- {area_label}{pitfall.description}")
            if pitfall.recommendation:
                lines.append(f"  - *{pitfall.recommendation}*")
        lines.append("")

    # ── Error Mapping ─────────────────────────────────────────────────
    if blueprint.quick_reference.error_mapping:
        lines.append("## Error Mapping")
        lines.append("")
        lines.append("| Error | Status Code |")
        lines.append("|-------|------------|")
        for em in blueprint.quick_reference.error_mapping:
            lines.append(f"| `{em.error}` | {em.status_code} |")
        lines.append("")

    # ── Frontend Quick Reference ──────────────────────────────────────
    fe = blueprint.frontend
    has_frontend = fe.framework or fe.ui_components or fe.routing or fe.data_fetching

    if has_frontend:
        lines.append("## Frontend Architecture")
        lines.append("")
        if fe.framework:
            lines.append(f"**Framework:** {fe.framework}")
            lines.append("")
        if fe.rendering_strategy:
            lines.append(f"**Rendering:** {fe.rendering_strategy}")
            lines.append("")
        if fe.styling:
            lines.append(f"**Styling:** {fe.styling}")
            lines.append("")
        sm = fe.state_management
        if sm.approach:
            lines.append(f"**State management:** {sm.approach}")
            if sm.server_state:
                lines.append(f"  - Server state: {sm.server_state}")
            if sm.local_state:
                lines.append(f"  - Local state: {sm.local_state}")
            lines.append("")
        if fe.key_conventions:
            lines.append("**Conventions:**")
            for conv in fe.key_conventions:
                lines.append(f"- {conv}")
            lines.append("")

    # ── Architecture MCP Server (MANDATORY) ──────────────────────────
    lines.append("## Architecture MCP Server (MANDATORY)")
    lines.append("")
    lines.append("The `architecture-blueprints` MCP server is the single source of truth for this codebase's architecture.")
    lines.append("You MUST call its tools for every architecture decision — no exceptions.")
    lines.append("")
    lines.append("**CRITICAL RULES:**")
    lines.append("")
    lines.append("1. **Before creating any new file**, call `where_to_put` to get the correct location.")
    lines.append("2. **Before naming any new component** (class, function, module, file), call `check_naming` to verify it follows conventions.")
    lines.append("3. **Before implementing a feature that may already exist**, call `how_to_implement` to check for existing patterns.")
    lines.append("4. **Never skip these checks.** Even if you believe you know the answer, the MCP server is authoritative.")
    lines.append("")
    lines.append("| Tool | When to Use | Required |")
    lines.append("|------|------------|----------|")
    lines.append("| `where_to_put` | Creating or moving any file | **Always** |")
    lines.append("| `check_naming` | Naming any new component | **Always** |")
    lines.append("| `how_to_implement` | Implementing a feature that may already exist | **Always** |")
    lines.append("| `get_file_content` | Reading source files referenced in guidelines | As needed |")
    lines.append("| `list_source_files` | Browsing available source files | As needed |")
    lines.append("| `get_repository_blueprint` | Understanding overall architecture | As needed |")
    lines.append("")
    lines.append("### Recommended Workflow")
    lines.append("")
    lines.append("When implementing a new feature:")
    lines.append("")
    lines.append("1. Call `how_to_implement` to check if a similar capability already exists")
    lines.append("2. If key files are listed, call `get_file_content` to study the existing implementation")
    lines.append("3. Call `where_to_put` to find the correct location for new files")
    lines.append("4. Call `check_naming` to validate your component names")
    lines.append("")
    lines.append("> If a tool rejects a decision, do NOT proceed — fix the violation first.")
    lines.append("")

    # ── Footer ────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("*Auto-generated from structured architecture analysis. Place in project root.*")

    return "\n".join(lines)


def generate_cursor_rules(blueprint: StructuredBlueprint) -> str:
    """Generate .cursor/rules/architecture.md from structured blueprint data.

    Cursor reads this file automatically and applies the rules when
    generating code via AI features.
    """
    repo = blueprint.meta.repository or "Unknown Repository"
    style = blueprint.meta.architecture_style or "Not determined"

    # Auto-detect globs from the technology stack
    globs = _detect_globs(blueprint)
    globs_str = ", ".join(f'"{g}"' for g in globs) if globs else '"**/*"'

    lines: list[str] = []

    # ── Frontmatter ───────────────────────────────────────────────────
    lines.append("---")
    lines.append(f"description: Architecture rules for {repo}")
    lines.append(f"globs: [{globs_str}]")
    lines.append("---")
    lines.append("")

    # ── Overview ──────────────────────────────────────────────────────
    lines.append(f"# {repo} Architecture Rules")
    lines.append("")
    lines.append(f"**Architecture style:** {style}")
    lines.append("")

    # ── Structure ─────────────────────────────────────────────────────
    if blueprint.components.components:
        lines.append("## Components")
        lines.append("")
        for comp in blueprint.components.components:
            lines.append(f"### {comp.name}")
            lines.append(f"- **Location:** `{comp.location}`")
            lines.append(f"- **Responsibility:** {comp.responsibility}")
            if comp.depends_on:
                lines.append(f"- **Depends on:** {', '.join(comp.depends_on)}")
            lines.append("")

    # ── File Placement ────────────────────────────────────────────────
    if blueprint.architecture_rules.file_placement_rules:
        lines.append("## File Placement")
        lines.append("")
        for fp in blueprint.architecture_rules.file_placement_rules:
            lines.append(f"- **{fp.component_type}** → `{fp.location}` (pattern: `{fp.naming_pattern}`)")
        lines.append("")

    # ── Naming Conventions ────────────────────────────────────────────
    if blueprint.architecture_rules.naming_conventions:
        lines.append("## Naming Conventions")
        lines.append("")
        for nc in blueprint.architecture_rules.naming_conventions:
            examples = ", ".join(f"`{e}`" for e in nc.examples[:3])
            lines.append(f"- **{nc.scope}**: {nc.pattern} — e.g. {examples}")
        lines.append("")

    # ── Patterns ──────────────────────────────────────────────────────
    if blueprint.communication.patterns:
        lines.append("## Communication Patterns")
        lines.append("")
        for pat in blueprint.communication.patterns:
            lines.append(f"### {pat.name}")
            lines.append(f"- **When:** {pat.when_to_use}")
            lines.append(f"- **How:** {pat.how_it_works}")
            lines.append("")

    # ── Developer Recipes ─────────────────────────────────────────────
    if blueprint.developer_recipes:
        lines.append("## Developer Recipes")
        lines.append("")
        for recipe in blueprint.developer_recipes:
            if not recipe.task:
                continue
            lines.append(f"### {recipe.task}")
            if recipe.files:
                lines.append(f"Files: {', '.join(f'`{f}`' for f in recipe.files)}")
            if recipe.steps:
                for i, step in enumerate(recipe.steps, 1):
                    lines.append(f"{i}. {step}")
            lines.append("")

    # ── Implementation Guidelines (compact) ────────────────────────────
    if blueprint.implementation_guidelines:
        lines.append("## Implementation Guidelines")
        lines.append("")
        for gl in blueprint.implementation_guidelines:
            if not gl.capability:
                continue
            libs = f" ({', '.join(gl.libraries)})" if gl.libraries else ""
            files = f" — {', '.join(f'`{f}`' for f in gl.key_files[:3])}" if gl.key_files else ""
            desc = f": {gl.pattern_description}" if gl.pattern_description else ""
            lines.append(f"- **{gl.capability}**{libs}{desc}{files}")
        lines.append("")

    # ── Frontend ──────────────────────────────────────────────────────
    fe = blueprint.frontend
    if fe.framework or fe.ui_components or fe.data_fetching:
        lines.append("## Frontend Architecture")
        lines.append("")
        if fe.framework:
            lines.append(f"- **Framework:** {fe.framework}")
        if fe.rendering_strategy:
            lines.append(f"- **Rendering:** {fe.rendering_strategy}")
        if fe.styling:
            lines.append(f"- **Styling:** {fe.styling}")
        sm = fe.state_management
        if sm.approach:
            lines.append(f"- **State management:** {sm.approach}")
        if fe.key_conventions:
            for conv in fe.key_conventions:
                lines.append(f"- {conv}")
        lines.append("")

    # ── Where to Put Code (quick reference) ───────────────────────────
    if blueprint.quick_reference.where_to_put_code:
        lines.append("## Where to Put Code")
        lines.append("")
        for comp_type, loc in blueprint.quick_reference.where_to_put_code.items():
            lines.append(f"- **{comp_type}** → `{loc}`")
        lines.append("")

    # ── Pattern Selection (quick reference) ─────────────────────────
    if blueprint.quick_reference.pattern_selection:
        lines.append("## Pattern Selection")
        lines.append("")
        for scenario, pattern in blueprint.quick_reference.pattern_selection.items():
            lines.append(f"- **{scenario}** → {pattern}")
        lines.append("")

    # ── Pitfalls ──────────────────────────────────────────────────────
    if blueprint.pitfalls:
        lines.append("## Pitfalls")
        lines.append("")
        for pitfall in blueprint.pitfalls:
            if not pitfall.area and not pitfall.description:
                continue
            area_label = f"**{pitfall.area}:** " if pitfall.area else ""
            lines.append(f"- {area_label}{pitfall.description}")
            if pitfall.recommendation:
                lines.append(f"  - *{pitfall.recommendation}*")
        lines.append("")

    # ── Error Mapping ─────────────────────────────────────────────────
    if blueprint.quick_reference.error_mapping:
        lines.append("## Error Mapping")
        lines.append("")
        lines.append("| Error | Status Code |")
        lines.append("|-------|------------|")
        for em in blueprint.quick_reference.error_mapping:
            lines.append(f"| `{em.error}` | {em.status_code} |")
        lines.append("")

    # ── Architecture MCP Server (MANDATORY) ──────────────────────────
    lines.append("## Architecture MCP Server (MANDATORY)")
    lines.append("")
    lines.append("The `architecture-blueprints` MCP server is the single source of truth for this codebase's architecture.")
    lines.append("You MUST call its tools for every architecture decision — no exceptions.")
    lines.append("")
    lines.append("| Tool | When to Use | Required |")
    lines.append("|------|------------|----------|")
    lines.append("| `where_to_put` | Creating or moving any file | **Always** |")
    lines.append("| `check_naming` | Naming any new component | **Always** |")
    lines.append("| `how_to_implement` | Implementing a feature that may already exist | **Always** |")
    lines.append("| `get_file_content` | Reading source files referenced in guidelines | As needed |")
    lines.append("| `list_source_files` | Browsing available source files | As needed |")
    lines.append("| `get_repository_blueprint` | Understanding overall architecture | As needed |")
    lines.append("")
    lines.append("**Before writing any code, you are REQUIRED to:**")
    lines.append("")
    lines.append("1. Call `how_to_implement` to check if a similar capability already exists.")
    lines.append("2. If key files are listed, call `get_file_content` to study the existing implementation.")
    lines.append("3. Call `where_to_put` before creating or moving any file.")
    lines.append("4. Call `check_naming` before naming any new component (class, function, module, file).")
    lines.append("")
    lines.append("**Never skip these checks.** The MCP server is authoritative.")
    lines.append("If a tool rejects a decision, do NOT proceed — fix the violation first.")
    lines.append("")

    # ── Footer ────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("*Auto-generated from structured architecture analysis.*")

    return "\n".join(lines)


def generate_agents_md(blueprint: StructuredBlueprint) -> str:
    """Generate AGENTS.md from structured blueprint data."""
    timestamp = datetime.now(timezone.utc).isoformat()
    repo = blueprint.meta.repository or "Unknown Repository"
    repo_id = blueprint.meta.repository_id or ""

    lines: list[str] = []

    lines.append("# AGENTS.md")
    lines.append("")
    lines.append(f"> Multi-agent system guidance for **{repo}**")
    lines.append(f"> Repository ID: {repo_id}")
    lines.append(f"> Generated: {timestamp}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Blueprint sections overview
    sections = []
    if blueprint.decisions.architectural_style.chosen:
        sections.append(f"- Architecture: {blueprint.decisions.architectural_style.chosen}")
    if blueprint.components.components:
        sections.append(f"- Components: {len(blueprint.components.components)}")
    if blueprint.architecture_rules.file_placement_rules:
        sections.append(f"- File placement rules: {len(blueprint.architecture_rules.file_placement_rules)}")
    if blueprint.communication.patterns:
        sections.append(f"- Communication patterns: {len(blueprint.communication.patterns)}")
    if blueprint.developer_recipes:
        sections.append(f"- Developer recipes: {len(blueprint.developer_recipes)}")
    if blueprint.pitfalls:
        sections.append(f"- Pitfalls: {len(blueprint.pitfalls)}")
    if blueprint.implementation_guidelines:
        sections.append(f"- Implementation guidelines: {len(blueprint.implementation_guidelines)}")

    if blueprint.meta.platforms:
        sections.append(f"- Platforms: {', '.join(blueprint.meta.platforms)}")
    fe = blueprint.frontend
    if fe.framework:
        sections.append(f"- Frontend framework: {fe.framework}")

    if sections:
        lines.append("## Blueprint Summary")
        lines.append("")
        lines.extend(sections)
        lines.append("")

    lines.append("## Architecture MCP Server (MANDATORY)")
    lines.append("")
    lines.append("The `architecture-blueprints` MCP server is the single source of truth for this codebase's architecture.")
    lines.append("ALL agents MUST call its tools for every architecture decision — no exceptions.")
    lines.append("")
    lines.append("### Required MCP Calls")
    lines.append("")
    lines.append("| Tool | When to Use | Required |")
    lines.append("|------|------------|----------|")
    lines.append("| `where_to_put` | Before creating or moving any file | **Always** |")
    lines.append("| `check_naming` | Before naming any new component | **Always** |")
    lines.append("| `how_to_implement` | Before implementing a feature that may already exist | **Always** |")
    lines.append("| `get_file_content` | Reading source files referenced in guidelines | As needed |")
    lines.append("| `list_source_files` | Browsing available source files | As needed |")
    lines.append("| `get_repository_blueprint` | To understand overall architecture | As needed |")
    lines.append("")
    lines.append("**If a tool rejects a decision, do NOT proceed — fix the violation first.**")
    lines.append("")

    lines.append("## Agent Roles")
    lines.append("")
    lines.append("### Architecture Analysis Agent")
    lines.append("- Analyzes codebase structure and patterns")
    lines.append("- Discovers actual architecture without predefined assumptions")
    lines.append("- Generates structured JSON blueprint as single source of truth")
    lines.append("")
    lines.append("### Code Generation Agent")
    lines.append("- MUST call `architecture-blueprints` MCP tools before every file creation and naming decision")
    lines.append("- Calls `how_to_implement` to check for existing patterns before building new features")
    lines.append("- Uses `get_file_content` to study referenced source files")
    lines.append("- Places new code in correct locations per `where_to_put` response")
    lines.append("- Verifies all names via `check_naming` before committing")
    lines.append("")
    lines.append("### Validation Agent")
    lines.append("- Uses `architecture-blueprints` MCP tools to validate code changes against architecture rules")
    lines.append("- Checks file locations and naming conventions via MCP")
    lines.append("- Reports violations with severity levels")
    lines.append("")

    lines.append("## Agent Workflow")
    lines.append("")
    lines.append("```")
    lines.append("1. Receive task")
    lines.append("2. Call how_to_implement to check for existing patterns")
    lines.append("3. If key files listed, call get_file_content to study them")
    lines.append("4. Call where_to_put for each new file → use returned path")
    lines.append("5. Call check_naming for each new name → fix before committing")
    lines.append("6. Submit code only after all checks pass")
    lines.append("```")
    lines.append("")

    lines.append("## File Placement")
    lines.append("")
    lines.append("- `CLAUDE.md` — Project root (AI assistant guidance)")
    lines.append("- `.cursor/rules/architecture.md` — Cursor IDE integration")
    lines.append("- `AGENTS.md` — Multi-agent system configuration")
    lines.append("")
    lines.append("---")
    lines.append("*Auto-generated from structured architecture analysis.*")

    return "\n".join(lines)


def _detect_globs(blueprint: StructuredBlueprint) -> list[str]:
    """Detect file extension globs from the technology stack."""
    ext_map = {
        "python": "**/*.py",
        "typescript": "**/*.ts",
        "javascript": "**/*.js",
        "java": "**/*.java",
        "go": "**/*.go",
        "rust": "**/*.rs",
        "swift": "**/*.swift",
        "kotlin": "**/*.kt",
        "ruby": "**/*.rb",
        "php": "**/*.php",
        "c#": "**/*.cs",
        "c++": "**/*.cpp",
    }

    globs = set()
    for entry in blueprint.technology.stack:
        name_lower = entry.name.lower()
        for lang, glob in ext_map.items():
            if lang in name_lower:
                globs.add(glob)

        # Also check for React/Next.js etc.
        if "react" in name_lower or "next" in name_lower:
            globs.add("**/*.tsx")
            globs.add("**/*.jsx")

    # Check file placement rules for extensions
    for fp in blueprint.architecture_rules.file_placement_rules:
        if fp.naming_pattern:
            ext = fp.naming_pattern.rsplit(".", 1)[-1] if "." in fp.naming_pattern else ""
            if ext and len(ext) <= 4:
                globs.add(f"**/*.{ext}")

    return sorted(globs) if globs else ["**/*"]
