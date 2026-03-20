"""Subagent planner: groups files into token-budgeted assignments."""
from __future__ import annotations

from dataclasses import dataclass, field

from archie.engine.models import RawScan

ALL_SECTIONS = [
    "architecture_rules",
    "decisions",
    "components",
    "communication",
    "quick_reference",
    "technology",
    "frontend",
    "developer_recipes",
    "pitfalls",
    "implementation_guidelines",
    "development_rules",
    "deployment",
]


@dataclass
class SubagentAssignment:
    """A group of files assigned to one subagent."""

    files: list[str] = field(default_factory=list)
    token_total: int = 0
    sections: list[str] = field(default_factory=list)
    module_hint: str = ""


def _top_level_dir(path: str) -> str:
    """Return the first path component as the module key."""
    parts = path.split("/")
    return parts[0] if len(parts) > 1 else ""


def plan_subagent_groups(
    scan: RawScan,
    token_budget: int = 150_000,
) -> list[SubagentAssignment]:
    """Split scanned files into token-budgeted subagent groups.

    Files are grouped by top-level directory.  If the total token count
    fits within *token_budget*, a single group is returned.  Otherwise
    modules are bin-packed into groups that each respect the budget.
    A module that exceeds the budget on its own gets its own group.
    Every group receives *ALL_SECTIONS* (the coordinator merges later).
    """
    if not scan.file_tree:
        return []

    # Collect per-file tokens keyed by path.
    token_counts = scan.token_counts

    # Build modules: top-level dir -> list of (path, tokens).
    modules: dict[str, list[tuple[str, int]]] = {}
    for entry in scan.file_tree:
        key = _top_level_dir(entry.path) or "__root__"
        tokens = token_counts.get(entry.path, 0)
        modules.setdefault(key, []).append((entry.path, tokens))

    # Total tokens across all files.
    total_tokens = sum(t for files in modules.values() for _, t in files)

    if total_tokens <= token_budget:
        all_files = [e.path for e in scan.file_tree]
        hint = ", ".join(sorted(modules.keys()))
        return [
            SubagentAssignment(
                files=all_files,
                token_total=total_tokens,
                sections=list(ALL_SECTIONS),
                module_hint=hint,
            )
        ]

    # Bin-pack modules into groups respecting the budget.
    # Sort modules largest-first for a better packing heuristic.
    module_items: list[tuple[str, list[tuple[str, int]], int]] = []
    for key, file_list in modules.items():
        mod_tokens = sum(t for _, t in file_list)
        module_items.append((key, file_list, mod_tokens))
    module_items.sort(key=lambda x: x[2], reverse=True)

    groups: list[SubagentAssignment] = []

    for mod_name, file_list, mod_tokens in module_items:
        placed = False
        # Try to fit into an existing group.
        for group in groups:
            if group.token_total + mod_tokens <= token_budget:
                group.files.extend(path for path, _ in file_list)
                group.token_total += mod_tokens
                group.module_hint += f", {mod_name}" if group.module_hint else mod_name
                placed = True
                break
        if not placed:
            # New group for this module (even if it exceeds budget).
            groups.append(
                SubagentAssignment(
                    files=[path for path, _ in file_list],
                    token_total=mod_tokens,
                    sections=list(ALL_SECTIONS),
                    module_hint=mod_name,
                )
            )

    # Ensure every group has sections assigned.
    for group in groups:
        if not group.sections:
            group.sections = list(ALL_SECTIONS)

    return groups
