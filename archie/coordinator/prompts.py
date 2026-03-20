"""Prompt builders for the coordinator (Opus) and subagents (Sonnet)."""
from __future__ import annotations

from collections import defaultdict

from archie.coordinator.planner import SubagentAssignment
from archie.engine.models import RawScan

# ---------------------------------------------------------------------------
# Schema guidance snippets for each blueprint section
# ---------------------------------------------------------------------------
_SECTION_GUIDANCE: dict[str, str] = {
    "components": (
        "List architectural components with name, purpose, key files, "
        "and relationships to other components."
    ),
    "architecture_rules": (
        "Describe enforced constraints: naming conventions, layer boundaries, "
        "dependency direction, and module encapsulation rules."
    ),
    "decisions": (
        "Capture key architectural decisions (ADR-style): context, decision, "
        "rationale, and consequences."
    ),
    "communication": (
        "Document how components communicate: sync (HTTP, gRPC), async "
        "(queues, events), and internal function calls across boundaries."
    ),
    "technology": (
        "List languages, frameworks, build tools, and infrastructure "
        "dependencies with versions where detectable."
    ),
    "frontend": (
        "Describe frontend architecture: component hierarchy, state "
        "management, routing, styling approach, and build pipeline."
    ),
    "implementation_guidelines": (
        "Document how existing capabilities were built: libraries used, "
        "integration patterns, key files, and extension points."
    ),
    "deployment": (
        "Describe deployment targets, CI/CD pipelines, container setup, "
        "environment configuration, and release process."
    ),
    "developer_recipes": (
        "Provide step-by-step recipes for common tasks: adding a feature, "
        "running tests, debugging, and deploying."
    ),
    "pitfalls": (
        "List non-obvious gotchas, common mistakes, implicit coupling, "
        "and areas where the code contradicts expectations."
    ),
    "development_rules": (
        "Summarise code-style rules, PR conventions, branch strategy, "
        "and any linter/formatter configuration."
    ),
}


# ---------------------------------------------------------------------------
# Coordinator prompt
# ---------------------------------------------------------------------------


def build_coordinator_prompt(
    scan: RawScan,
    groups: list[SubagentAssignment],
) -> str:
    """Build the system prompt for the Opus coordinator.

    The coordinator never reads source code directly.  It receives reports
    from subagents and merges them into a single StructuredBlueprint JSON.
    """
    frameworks = ", ".join(f.name for f in scan.framework_signals) or "none detected"
    total_files = len(scan.file_tree)
    total_tokens = sum(scan.token_counts.values())
    entry_points = ", ".join(scan.entry_points[:20]) or "none detected"

    # Dependencies (cap at 50)
    dep_lines = [f"  - {d.name} {d.version}".strip() for d in scan.dependencies[:50]]
    deps_block = "\n".join(dep_lines) if dep_lines else "  (none)"

    # File tree (cap at 200)
    tree_lines = [f"  {e.path}" for e in scan.file_tree[:200]]
    tree_block = "\n".join(tree_lines) if tree_lines else "  (empty)"

    # Subagent group summary
    group_lines: list[str] = []
    for i, g in enumerate(groups, 1):
        group_lines.append(
            f"  Group {i}: {len(g.files)} files, "
            f"{g.token_total} tokens, module: {g.module_hint or 'mixed'}"
        )
    groups_block = "\n".join(group_lines) if group_lines else "  (no groups)"

    return f"""\
You are the architecture coordinator for a repository analysis.

## Repository summary
- Detected frameworks: {frameworks}
- Total files: {total_files}
- Total tokens: {total_tokens}
- Entry points: {entry_points}

## Dependencies
{deps_block}

## File tree
{tree_block}

## Subagent groups
{groups_block}

## Instructions
You do NOT read source code yourself.  You will receive reports from
subagent analysts — one per group listed above.  Your responsibilities:

1. Merge all subagent reports into a single StructuredBlueprint JSON object.
2. Resolve contradictions between reports (prefer the report with more
   evidence or higher-confidence signals).
3. Fill cross-cutting sections that no single subagent can determine alone
   (e.g. communication patterns across module boundaries, overall
   architecture_rules, deployment topology).
4. Ensure every section of the blueprint is populated; mark sections as
   "not detected" only when no subagent provided relevant data.
5. Output valid JSON conforming to the StructuredBlueprint schema.
"""


# ---------------------------------------------------------------------------
# Import graph helpers
# ---------------------------------------------------------------------------


def _top_level_module(path: str) -> str:
    """Return the first path component as the module name."""
    parts = path.split("/")
    return parts[0] if len(parts) > 1 else ""


def _module_dependencies(
    assignment: SubagentAssignment,
    scan: RawScan,
) -> tuple[set[str], set[str], list[str]]:
    """Compute cross-module dependency info for a subagent assignment.

    Returns:
        imports_from: set of module names this assignment's files import from
        imported_by: set of module names that import from this assignment's files
        entry_points: files in this assignment that appear in scan.entry_points
    """
    assigned_set = set(assignment.files)
    # Determine which modules the assigned files belong to.
    own_modules: set[str] = set()
    for f in assignment.files:
        mod = _top_level_module(f)
        if mod:
            own_modules.add(mod)

    imports_from: set[str] = set()
    imported_by: set[str] = set()

    for source_file, targets in scan.import_graph.items():
        source_mod = _top_level_module(source_file)

        if source_file in assigned_set:
            # This file belongs to our assignment — its targets are our deps.
            for target in targets:
                target_mod = _top_level_module(target)
                if target_mod and target_mod not in own_modules:
                    imports_from.add(target_mod)
        else:
            # External file — check if it imports from our assignment's files.
            for target in targets:
                if target in assigned_set:
                    if source_mod and source_mod not in own_modules:
                        imported_by.add(source_mod)

    entry_points = [f for f in assignment.files if f in scan.entry_points]

    return imports_from, imported_by, entry_points


# ---------------------------------------------------------------------------
# Subagent prompt
# ---------------------------------------------------------------------------


def build_subagent_prompt(
    assignment: SubagentAssignment,
    scan: RawScan,
) -> str:
    """Build the system prompt for a Sonnet subagent.

    Each subagent reads the files in its assignment and fills the requested
    blueprint sections with structured JSON.
    """
    frameworks = ", ".join(f.name for f in scan.framework_signals) or "none detected"

    dep_names = ", ".join(d.name for d in scan.dependencies[:50]) or "none"

    file_list = "\n".join(f"  - {f}" for f in assignment.files) or "  (none)"

    section_list = "\n".join(f"  - {s}" for s in assignment.sections) or "  (none)"

    # Build schema guidance for the assigned sections
    guidance_lines: list[str] = []
    for section in assignment.sections:
        hint = _SECTION_GUIDANCE.get(section, "Populate according to schema.")
        guidance_lines.append(f"### {section}\n{hint}")
    guidance_block = "\n\n".join(guidance_lines)

    # Module dependency context from import graph
    imports_from, imported_by, entry_points = _module_dependencies(assignment, scan)
    dep_section_lines: list[str] = []
    if imports_from:
        dep_section_lines.append(
            "- Imports from modules: " + ", ".join(sorted(imports_from))
        )
    if imported_by:
        dep_section_lines.append(
            "- Imported by modules: " + ", ".join(sorted(imported_by))
        )
    if entry_points:
        dep_section_lines.append(
            "- Entry points: " + ", ".join(entry_points)
        )
    module_deps_block = ""
    if dep_section_lines:
        module_deps_block = (
            "\n## Module Dependencies\n" + "\n".join(dep_section_lines) + "\n"
        )

    return f"""\
You are a code analyst subagent responsible for module: {assignment.module_hint or 'general'}.

## Context
- Detected frameworks: {frameworks}
- Known dependencies: {dep_names}
- Assigned module: {assignment.module_hint or 'general'}
{module_deps_block}
## Files to read
{file_list}

## Blueprint sections to fill
{section_list}

## Schema guidance per section

{guidance_block}

## Output format
Return a valid JSON dict keyed by section name.  Each key must be one of the
section names listed above.  Example:

```json
{{
  "components": [...],
  "technology": {{...}}
}}
```

## Focus
Concentrate on architectural insights that an AI cannot infer from
individual files in isolation: cross-file relationships, implicit contracts,
non-obvious design decisions, and integration patterns.
"""
