"""Generate agent instruction files (CLAUDE.md, Cursor rules) from structured blueprint JSON.

All outputs derive from the same StructuredBlueprint, ensuring consistency
across CLAUDE.md, Cursor rules, MCP tools, and the human-readable markdown.

The primary entry point is ``generate_all()`` which produces a ``GeneratedOutput``
containing the lean root CLAUDE.md, AGENTS.md, and topic-split rule files for
both ``.claude/rules/`` and ``.cursor/rules/``.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _clean_str_item(s: str) -> str:
    """Clean a stringified Python dict back into readable text."""
    stripped = s.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return s
    try:
        obj = ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        return s
    if not isinstance(obj, dict):
        return s
    parts = []
    for k, v in obj.items():
        if isinstance(v, list):
            parts.append(f"{k}: {', '.join(str(x) for x in v)}")
        elif v:
            parts.append(f"{k}: {v}")
    return "; ".join(parts)

from collections import defaultdict

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
    body = """## Archie MCP Server (MANDATORY)

The `archie` MCP server is the single source of truth for this codebase's architecture.
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
        description="Archie MCP server usage rules",
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


def _build_dev_rules_rule(blueprint: StructuredBlueprint) -> Optional[RuleFile]:
    """Build the dev-rules rule: imperative development rules grouped by category."""
    if not blueprint.development_rules:
        return None

    by_category: dict[str, list] = defaultdict(list)
    for dr in blueprint.development_rules:
        cat = dr.category.strip() or "general"
        by_category[cat].append(dr)

    lines: list[str] = []
    lines.append("## Development Rules")
    lines.append("")

    for cat_name in sorted(by_category.keys()):
        heading = cat_name.replace("_", " ").title()
        lines.append(f"### {heading}")
        lines.append("")
        for dr in by_category[cat_name]:
            if dr.source:
                lines.append(f"- {dr.rule} *(source: `{dr.source}`)*")
            else:
                lines.append(f"- {dr.rule}")
        lines.append("")

    return RuleFile(
        topic="dev-rules",
        body="\n".join(lines).rstrip(),
        description="Development rules: imperative do/don't rules from codebase signals",
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

    # Deployment
    dep = blueprint.deployment
    if dep.runtime_environment:
        lines.append(f"**Runs on:** {dep.runtime_environment}")
        if dep.compute_services:
            lines.append(f"**Compute:** {', '.join(dep.compute_services)}")
        if dep.ci_cd:
            cleaned = [_clean_str_item(x) for x in dep.ci_cd]
            lines.append(f"**CI/CD:** {', '.join(cleaned)}")
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
    lines.append("- `dev-rules.md` — Development rules (always/never imperatives)")
    lines.append("- `mcp-tools.md` — MCP server tool reference")
    lines.append("- `frontend.md` — Frontend rules (when applicable)")
    lines.append("")

    # MCP mandatory note
    lines.append("## Archie MCP Server (MANDATORY)")
    lines.append("")
    lines.append("The `archie` MCP server is the single source of truth.")
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
        _build_dev_rules_rule,
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
    """Generate AGENTS.md following GitHub's 6 core areas for effective agent files.

    Structure (commands early, boundaries clear, examples over prose):
    1. Tech Stack — specific versions
    2. Commands — executable, with flags
    3. Project Structure
    4. Code Style — concrete examples from templates
    5. Development Rules — imperative always/never
    6. Boundaries — three-tier (always/ask/never)
    7. Testing
    8. Common Workflows
    9. Pitfalls
    10. Archie MCP Server
    """
    import re

    timestamp = datetime.now(timezone.utc).isoformat()
    repo = blueprint.meta.repository or "Unknown Repository"

    lines: list[str] = []

    lines.append("# AGENTS.md")
    lines.append("")
    lines.append(f"> Agent guidance for **{repo}**")
    lines.append(f"> Generated: {timestamp}")
    lines.append("")

    # ── Overview ──
    if blueprint.meta.executive_summary:
        lines.append(blueprint.meta.executive_summary)
        lines.append("")

    lines.append("---")
    lines.append("")

    # ── 1. Tech Stack (specific versions, not vague) ──
    if blueprint.technology.stack:
        lines.append("## Tech Stack")
        lines.append("")
        # Group by category for a compact summary line
        by_cat: dict[str, list[str]] = defaultdict(list)
        for entry in blueprint.technology.stack:
            version = f" {entry.version}" if entry.version else ""
            by_cat[entry.category].append(f"{entry.name}{version}")
        for cat in sorted(by_cat.keys()):
            techs = ", ".join(by_cat[cat])
            lines.append(f"- **{cat}:** {techs}")
        lines.append("")

    # ── 2. Deployment (where it runs) ──
    dep = blueprint.deployment
    has_deployment = dep.runtime_environment or dep.compute_services or dep.ci_cd
    if has_deployment:
        lines.append("## Deployment")
        lines.append("")
        if dep.runtime_environment:
            lines.append(f"**Runs on:** {dep.runtime_environment}")
        if dep.compute_services:
            lines.append(f"**Compute:** {', '.join(dep.compute_services)}")
        if dep.container_runtime:
            container = dep.container_runtime
            if dep.orchestration:
                container += f" + {dep.orchestration}"
            lines.append(f"**Container:** {container}")
        if dep.ci_cd:
            lines.append("**CI/CD:**")
            for item in dep.ci_cd:
                lines.append(f"- {_clean_str_item(item)}")
        if dep.distribution:
            lines.append("**Distribution:**")
            for item in dep.distribution:
                lines.append(f"- {_clean_str_item(item)}")
        lines.append("")

    # ── 3. Commands (early, with flags — most referenced section) ──
    if blueprint.technology.run_commands:
        lines.append("## Commands")
        lines.append("")
        lines.append("```bash")
        for cmd_name, cmd_value in blueprint.technology.run_commands.items():
            lines.append(f"# {cmd_name}")
            lines.append(cmd_value)
        lines.append("```")
        lines.append("")

    # ── 4. Project Structure ──
    if blueprint.technology.project_structure:
        lines.append("## Project Structure")
        lines.append("")
        lines.append("```")
        lines.append(blueprint.technology.project_structure)
        lines.append("```")
        lines.append("")

    # ── 5. Code Style (concrete examples beat prose) ──
    has_code_style = (
        blueprint.architecture_rules.naming_conventions
        or blueprint.technology.templates
    )
    if has_code_style:
        lines.append("## Code Style")
        lines.append("")

        # Naming conventions with examples
        if blueprint.architecture_rules.naming_conventions:
            for nc in blueprint.architecture_rules.naming_conventions:
                examples = ", ".join(f"`{e}`" for e in nc.examples[:4])
                lines.append(f"- **{nc.scope}:** {nc.pattern} (e.g. {examples})")
            lines.append("")

        # Code templates — real code snippets showing the project's style
        if blueprint.technology.templates:
            for tmpl in blueprint.technology.templates[:3]:
                if tmpl.code:
                    lines.append(f"### {tmpl.component_type}: {tmpl.description}")
                    lines.append("")
                    lines.append(f"File: `{tmpl.file_path_template}`")
                    lines.append("")
                    lines.append("```")
                    lines.append(tmpl.code)
                    lines.append("```")
                    lines.append("")

    # ── 6. Development Rules ──
    if blueprint.development_rules:
        by_rule_cat: dict[str, list] = defaultdict(list)
        for dr in blueprint.development_rules:
            cat = dr.category.strip() or "general"
            by_rule_cat[cat].append(dr)

        lines.append("## Development Rules")
        lines.append("")
        for cat_name in sorted(by_rule_cat.keys()):
            heading = cat_name.replace("_", " ").title()
            lines.append(f"### {heading}")
            lines.append("")
            for dr in by_rule_cat[cat_name]:
                if dr.source:
                    lines.append(f"- {dr.rule} *(source: `{dr.source}`)*")
                else:
                    lines.append(f"- {dr.rule}")
            lines.append("")

    # ── 7. Boundaries (three-tier: always / ask / never) ──
    lines.append("## Boundaries")
    lines.append("")
    lines.append("### Always")
    lines.append("")
    always_items = [
        "Run tests before committing",
        "Use `where_to_put` MCP tool before creating files",
        "Use `check_naming` MCP tool before naming components",
        "Follow file placement rules (see `.claude/rules/architecture.md`)",
    ]
    for item in always_items:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Ask First")
    lines.append("")
    ask_items = [
        "Database schema changes",
        "Adding new dependencies",
        "Modifying CI/CD configuration",
        "Changes to deployment configuration",
    ]
    for item in ask_items:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Never")
    lines.append("")
    never_items = [
        "Commit secrets or API keys",
        "Edit vendor/node_modules directories",
        "Remove failing tests without authorization",
    ]
    # Add project-specific nevers from pitfalls
    for pitfall in blueprint.pitfalls[:3]:
        if pitfall.recommendation and "never" in pitfall.recommendation.lower():
            never_items.append(pitfall.recommendation)
    for item in never_items:
        lines.append(f"- {item}")
    lines.append("")

    # ── 8. Testing ──
    test_commands = {k: v for k, v in blueprint.technology.run_commands.items()
                     if any(t in k.lower() for t in ("test", "lint", "check", "verify"))}
    test_stack = [e for e in blueprint.technology.stack
                  if e.category.lower() in ("testing", "linting")]
    if test_commands or test_stack:
        lines.append("## Testing")
        lines.append("")
        if test_stack:
            for entry in test_stack:
                version = f" {entry.version}" if entry.version else ""
                lines.append(f"- **{entry.name}{version}** — {entry.purpose}")
            lines.append("")
        if test_commands:
            lines.append("```bash")
            for cmd_name, cmd_value in test_commands.items():
                lines.append(f"# {cmd_name}")
                lines.append(cmd_value)
            lines.append("```")
            lines.append("")

    # ── 9. Common Workflows ──
    if blueprint.developer_recipes:
        lines.append("## Common Workflows")
        lines.append("")
        for recipe in blueprint.developer_recipes:
            if not recipe.task:
                continue
            lines.append(f"### {recipe.task}")
            if recipe.files:
                lines.append(f"Files: {', '.join(f'`{f}`' for f in recipe.files)}")
            if recipe.steps:
                for i, step in enumerate(recipe.steps, 1):
                    step = re.sub(r'^\d+[\.\)]\s*', '', step)
                    lines.append(f"{i}. {step}")
            lines.append("")

    # ── 10. Pitfalls & Gotchas ──
    if blueprint.pitfalls:
        lines.append("## Pitfalls & Gotchas")
        lines.append("")
        for pitfall in blueprint.pitfalls:
            if not pitfall.area and not pitfall.description:
                continue
            area_label = f"**{pitfall.area}:** " if pitfall.area else ""
            lines.append(f"- {area_label}{pitfall.description}")
            if pitfall.recommendation:
                lines.append(f"  - *{pitfall.recommendation}*")
        lines.append("")

    # ── 11. Archie MCP Server (at end, not top) ──
    lines.append("## Archie MCP Server")
    lines.append("")
    lines.append("The `archie` MCP server is the single source of truth.")
    lines.append("Call its tools for every architecture decision.")
    lines.append("")
    lines.append("| Tool | When to Use |")
    lines.append("|------|------------|")
    lines.append("| `where_to_put` | Before creating or moving any file |")
    lines.append("| `check_naming` | Before naming any new component |")
    lines.append("| `list_implementations` | Discovering available implementation patterns |")
    lines.append("| `how_to_implement_by_id` | Getting full details for a specific capability |")
    lines.append("| `how_to_implement` | Fuzzy search when exact capability name unknown |")
    lines.append("| `get_file_content` | Reading source files referenced in guidelines |")
    lines.append("")

    # ── File Placement Quick Reference ──
    if blueprint.quick_reference.where_to_put_code:
        lines.append("## File Placement")
        lines.append("")
        for comp_type, loc in blueprint.quick_reference.where_to_put_code.items():
            lines.append(f"- **{comp_type}** → `{loc}`")
        lines.append("")

    lines.append("---")
    lines.append("*Auto-generated from structured architecture analysis.*")

    return "\n".join(lines)
