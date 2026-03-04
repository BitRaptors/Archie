"""Generate agent instruction files (CLAUDE.md, Cursor rules) from structured blueprint JSON.

All outputs derive from the same StructuredBlueprint, ensuring consistency
across CLAUDE.md, Cursor rules, MCP tools, and the human-readable markdown.

The primary entry point is ``generate_all()`` which produces a ``GeneratedOutput``
containing the lean root CLAUDE.md, AGENTS.md, and topic-split rule files for
both ``.claude/rules/`` and ``.cursor/rules/``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from domain.entities.blueprint import StructuredBlueprint


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RuleFile:
    """A single topic-split rule file that renders with platform-specific frontmatter."""

    topic: str
    body: str
    description: str = ""
    always_apply: bool = True
    globs: list[str] = field(default_factory=list)

    @property
    def claude_path(self) -> str:
        return f".claude/rules/{self.topic}.md"

    @property
    def cursor_path(self) -> str:
        return f".cursor/rules/{self.topic}.md"

    def render_claude(self) -> str:
        """Render for Claude Code (.claude/rules/).

        Adds ``paths:`` YAML frontmatter when globs are present.
        """
        if self.globs:
            globs_yaml = "\n".join(f"  - {g}" for g in self.globs)
            return f"---\npaths:\n{globs_yaml}\n---\n\n{self.body}"
        return self.body

    def render_cursor(self) -> str:
        """Render for Cursor (.cursor/rules/).

        Always adds Cursor-style YAML frontmatter with description,
        globs (if scoped), and alwaysApply.
        """
        lines = ["---"]
        if self.description:
            lines.append(f"description: {self.description}")
        if self.globs:
            globs_str = ", ".join(f'"{g}"' for g in self.globs)
            lines.append(f"globs: [{globs_str}]")
            lines.append("alwaysApply: false")
        else:
            lines.append(f"alwaysApply: {str(self.always_apply).lower()}")
        lines.append("---")
        lines.append("")
        lines.append(self.body)
        return "\n".join(lines)


@dataclass
class GeneratedOutput:
    """All generated files from a single blueprint."""

    claude_md: str
    agents_md: str
    rule_files: list[RuleFile] = field(default_factory=list)

    def to_file_map(self) -> dict[str, str]:
        """Build ``{path: rendered_content}`` for every output file."""
        files: dict[str, str] = {
            "CLAUDE.md": self.claude_md,
            "AGENTS.md": self.agents_md,
        }
        for rf in self.rule_files:
            files[rf.claude_path] = rf.render_claude()
            files[rf.cursor_path] = rf.render_cursor()
        return files


# ---------------------------------------------------------------------------
# Topic builders
# ---------------------------------------------------------------------------

def _build_architecture_rule(blueprint: StructuredBlueprint) -> Optional[RuleFile]:
    """Build the architecture rule: components, file placement, naming, where-to-put."""
    lines: list[str] = []

    # Components
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

    # File Placement
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

    # Where to Put Code
    if blueprint.quick_reference.where_to_put_code:
        lines.append("## Where to Put Code")
        lines.append("")
        for comp_type, loc in blueprint.quick_reference.where_to_put_code.items():
            lines.append(f"- **{comp_type}** -> `{loc}`")
        lines.append("")

    # Naming Conventions
    if blueprint.architecture_rules.naming_conventions:
        lines.append("## Naming Conventions")
        lines.append("")
        for nc in blueprint.architecture_rules.naming_conventions:
            examples = ", ".join(f"`{e}`" for e in nc.examples[:4])
            lines.append(f"- **{nc.scope}**: {nc.pattern} (e.g. {examples})")
        lines.append("")

    if not lines:
        return None

    return RuleFile(
        topic="architecture",
        body="\n".join(lines).rstrip(),
        description="Architecture rules: components, file placement, naming conventions",
        always_apply=True,
    )


def _build_patterns_rule(blueprint: StructuredBlueprint) -> Optional[RuleFile]:
    """Build the patterns rule: communication patterns, pattern selection, decisions."""
    lines: list[str] = []

    # Communication Patterns
    if blueprint.communication.patterns:
        lines.append("## Communication Patterns")
        lines.append("")
        for pat in blueprint.communication.patterns:
            lines.append(f"### {pat.name}")
            lines.append(f"- **When:** {pat.when_to_use}")
            lines.append(f"- **How:** {pat.how_it_works}")
            lines.append("")

    # Pattern Selection Guide
    if blueprint.communication.pattern_selection_guide:
        lines.append("## Pattern Selection Guide")
        lines.append("")
        lines.append("| Scenario | Pattern | Rationale |")
        lines.append("|----------|---------|-----------|")
        for psg in blueprint.communication.pattern_selection_guide:
            lines.append(f"| {psg.scenario} | {psg.pattern} | {psg.rationale} |")
        lines.append("")

    # Quick Reference: Pattern Selection
    if blueprint.quick_reference.pattern_selection:
        lines.append("## Quick Pattern Lookup")
        lines.append("")
        for scenario, pattern in blueprint.quick_reference.pattern_selection.items():
            lines.append(f"- **{scenario}** -> {pattern}")
        lines.append("")

    # Key Decisions
    if blueprint.decisions.key_decisions:
        lines.append("## Key Decisions")
        lines.append("")
        for dec in blueprint.decisions.key_decisions:
            lines.append(f"### {dec.title}")
            lines.append(f"**Chosen:** {dec.chosen}")
            if dec.rationale:
                lines.append(f"**Rationale:** {dec.rationale}")
            lines.append("")

    if not lines:
        return None

    return RuleFile(
        topic="patterns",
        body="\n".join(lines).rstrip(),
        description="Communication and design patterns, key architectural decisions",
        always_apply=True,
    )


def _build_frontend_rule(blueprint: StructuredBlueprint) -> Optional[RuleFile]:
    """Build the frontend rule: framework, rendering, styling, state, conventions."""
    fe = blueprint.frontend
    has_frontend = fe.framework or fe.ui_components or fe.routing or fe.data_fetching

    if not has_frontend:
        return None

    lines: list[str] = []
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

    globs = _detect_frontend_globs(blueprint)

    return RuleFile(
        topic="frontend",
        body="\n".join(lines).rstrip(),
        description="Frontend architecture rules",
        always_apply=False,
        globs=globs,
    )


def _build_mcp_tools_rule(_blueprint: StructuredBlueprint) -> RuleFile:
    """Build the MCP tools rule: static tool table + workflow."""
    body = """## Architecture MCP Server (MANDATORY)

The `architecture-blueprints` MCP server is the single source of truth for this codebase's architecture.
You MUST call its tools for every architecture decision — no exceptions.

| Tool | When to Use | Required |
|------|------------|----------|
| `where_to_put` | Creating or moving any file | **Always** |
| `check_naming` | Naming any new component | **Always** |
| `list_implementations` | Discovering available implementation patterns | **Always** |
| `how_to_implement_by_id` | Getting full details for a specific capability | **Always** |
| `how_to_implement` | Fuzzy search when exact capability name unknown | Fallback |
| `get_file_content` | Reading source files referenced in guidelines | As needed |
| `list_source_files` | Browsing available source files | As needed |
| `get_repository_blueprint` | Understanding overall architecture | As needed |

### Workflow

1. Call `list_implementations` to see all known patterns
2. Match task to capability, call `how_to_implement_by_id` with its ID
3. Fall back to `how_to_implement` with keyword search if no match
4. Call `get_file_content` to study referenced source files
5. Call `where_to_put` before creating any file
6. Call `check_naming` before naming any component

> If a tool rejects a decision, do NOT proceed — fix the violation first."""

    return RuleFile(
        topic="mcp-tools",
        body=body,
        description="Architecture MCP server usage rules",
        always_apply=True,
    )


def _build_recipes_rule(blueprint: StructuredBlueprint) -> Optional[RuleFile]:
    """Build the recipes rule: developer recipes + implementation guidelines."""
    lines: list[str] = []

    # Developer Recipes
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

    # Implementation Guidelines
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

    if not lines:
        return None

    return RuleFile(
        topic="recipes",
        body="\n".join(lines).rstrip(),
        description="Developer recipes and implementation guidelines",
        always_apply=True,
    )


def _build_pitfalls_rule(blueprint: StructuredBlueprint) -> Optional[RuleFile]:
    """Build the pitfalls rule: pitfalls + error mapping."""
    lines: list[str] = []

    # Pitfalls
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

    # Error Mapping
    if blueprint.quick_reference.error_mapping:
        lines.append("## Error Mapping")
        lines.append("")
        lines.append("| Error | Status Code |")
        lines.append("|-------|------------|")
        for em in blueprint.quick_reference.error_mapping:
            lines.append(f"| `{em.error}` | {em.status_code} |")
        lines.append("")

    if not lines:
        return None

    return RuleFile(
        topic="pitfalls",
        body="\n".join(lines).rstrip(),
        description="Common pitfalls and error mapping",
        always_apply=True,
    )


# ---------------------------------------------------------------------------
# Frontend glob detection
# ---------------------------------------------------------------------------

_FRONTEND_GLOB_MAP: dict[str, list[str]] = {
    "react": ["**/*.tsx", "**/*.jsx"],
    "next": ["**/*.tsx", "**/*.jsx"],
    "vue": ["**/*.vue"],
    "svelte": ["**/*.svelte"],
    "angular": ["**/*.ts", "**/*.html"],
    "flutter": ["**/*.dart"],
    "swiftui": ["**/*.swift"],
    "swift": ["**/*.swift"],
    "kotlin": ["**/*.kt"],
    "react native": ["**/*.tsx", "**/*.jsx"],
}


def _detect_frontend_globs(blueprint: StructuredBlueprint) -> list[str]:
    """Return frontend-specific globs based on framework and tech stack."""
    globs: set[str] = set()

    # Check framework name
    fw = (blueprint.frontend.framework or "").lower()
    for key, patterns in _FRONTEND_GLOB_MAP.items():
        if key in fw:
            globs.update(patterns)

    # Check tech stack
    for entry in blueprint.technology.stack:
        name_lower = entry.name.lower()
        for key, patterns in _FRONTEND_GLOB_MAP.items():
            if key in name_lower:
                globs.update(patterns)

    return sorted(globs) if globs else ["**/*"]


# ---------------------------------------------------------------------------
# Lean root CLAUDE.md
# ---------------------------------------------------------------------------

def generate_claude_md_lean(blueprint: StructuredBlueprint) -> str:
    """Generate a lean root CLAUDE.md (<120 lines).

    Focuses on: repo identity, executive summary, commands, architecture style,
    and pointers to ``.claude/rules/`` for detailed rules.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    repo = blueprint.meta.repository or "Unknown Repository"
    style = blueprint.meta.architecture_style or "Not determined"

    lines: list[str] = []

    # Header
    lines.append("# CLAUDE.md")
    lines.append("")
    lines.append(f"> Architecture guidance for **{repo}**")
    lines.append(f"> Style: {style}")
    lines.append(f"> Generated: {timestamp}")
    lines.append("")

    # Executive Summary
    if blueprint.meta.executive_summary:
        lines.append("## Overview")
        lines.append("")
        lines.append(blueprint.meta.executive_summary)
        lines.append("")

    # Architecture style
    ad = blueprint.decisions.architectural_style
    if ad.chosen:
        lines.append("## Architecture")
        lines.append("")
        lines.append(f"**Style:** {ad.chosen}")
        if blueprint.components.structure_type:
            lines.append(f"**Structure:** {blueprint.components.structure_type}")
        if ad.rationale:
            lines.append("")
            lines.append(ad.rationale)
        lines.append("")

    # Commands
    if blueprint.technology.run_commands:
        lines.append("## Commands")
        lines.append("")
        lines.append("```bash")
        for cmd_name, cmd_value in blueprint.technology.run_commands.items():
            lines.append(f"# {cmd_name}")
            lines.append(cmd_value)
        lines.append("```")
        lines.append("")

    # Key Rules pointer
    lines.append("## Key Rules")
    lines.append("")
    lines.append("Detailed architecture rules are split into topic files under `.claude/rules/`:")
    lines.append("")
    lines.append("- `architecture.md` — Components, file placement, naming conventions")
    lines.append("- `patterns.md` — Communication patterns, key decisions")
    lines.append("- `recipes.md` — Developer recipes, implementation guidelines")
    lines.append("- `pitfalls.md` — Common pitfalls, error mapping")
    lines.append("- `mcp-tools.md` — MCP server tool reference")
    lines.append("- `frontend.md` — Frontend rules (when applicable)")
    lines.append("")

    # MCP mandatory note
    lines.append("## Architecture MCP Server (MANDATORY)")
    lines.append("")
    lines.append("The `architecture-blueprints` MCP server is the single source of truth.")
    lines.append("You MUST call `where_to_put` before creating files and `check_naming` before naming components.")
    lines.append("See `.claude/rules/mcp-tools.md` for the full tool reference and workflow.")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Auto-generated from structured architecture analysis. Place in project root.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

def generate_all(blueprint: StructuredBlueprint) -> GeneratedOutput:
    """Generate all output files from a blueprint.

    Returns a ``GeneratedOutput`` with the lean CLAUDE.md, AGENTS.md,
    and topic-split rule files for both Claude Code and Cursor.
    """
    rule_files: list[RuleFile] = []

    builders = [
        _build_architecture_rule,
        _build_patterns_rule,
        _build_frontend_rule,
        _build_mcp_tools_rule,
        _build_recipes_rule,
        _build_pitfalls_rule,
    ]

    for builder in builders:
        result = builder(blueprint)
        if result is not None:
            rule_files.append(result)

    return GeneratedOutput(
        claude_md=generate_claude_md_lean(blueprint),
        agents_md=generate_agents_md(blueprint),
        rule_files=rule_files,
    )


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
    lines.append("| `list_implementations` | Discovering available implementation patterns | **Always** |")
    lines.append("| `how_to_implement_by_id` | Getting full details for a specific capability | **Always** |")
    lines.append("| `how_to_implement` | Fuzzy search when exact capability name unknown | Fallback |")
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
    lines.append("2. Call list_implementations to see all known patterns")
    lines.append("3. Match task to capability using IDs and descriptions")
    lines.append("4. Call how_to_implement_by_id with matching ID")
    lines.append("5. Fall back to how_to_implement with keyword search if no match")
    lines.append("6. If key files listed, call get_file_content to study them")
    lines.append("7. Call where_to_put for each new file -> use returned path")
    lines.append("8. Call check_naming for each new name -> fix before committing")
    lines.append("9. Submit code only after all checks pass")
    lines.append("```")
    lines.append("")

    lines.append("## File Placement")
    lines.append("")
    lines.append("- `CLAUDE.md` — Project root (lean overview + commands)")
    lines.append("- `.claude/rules/` — Claude Code rule files (topic-split)")
    lines.append("- `.cursor/rules/` — Cursor IDE rule files (topic-split)")
    lines.append("- `AGENTS.md` — Multi-agent system configuration")
    lines.append("")
    lines.append("---")
    lines.append("*Auto-generated from structured architecture analysis.*")

    return "\n".join(lines)
