"""Canonical taxonomy of rule `kind` values.

The `kind` field on a rule names the conceptual *type* of the rule
(what it's about), independent of `severity_class` (how the hook
enforces it) and `topic` (which subject area page the rule renders to).

Importers: anything that produces, classifies, or validates rules.
Do not redefine these values inline — import from here so the enum
stays single-sourced.
"""
from __future__ import annotations

KINDS: tuple[str, ...] = (
    "decision",
    "pitfall",
    "tradeoff",
    "layering",
    "semantic_pattern",
    "file_placement",
    "naming_convention",
    "infrastructure",
    "coding_practice",
)

KIND_DESCRIPTIONS: dict[str, str] = {
    "decision": "Clarifies an invariant rooted in a key architectural decision; violating it breaks the constraint chain that justified the decision.",
    "pitfall": "Guards against a documented causal trap; walking into it produces a known failure mode.",
    "tradeoff": "Formalizes a violation signal from an explicit tradeoff; firing means the agent is undermining the property the tradeoff bought.",
    "layering": "Enforces a dependency direction or layer boundary; typically expressible as forbidden imports between modules or layers.",
    "semantic_pattern": "Captures a project-specific code shape from `components.patterns` or `implementation_guidelines`; divergence is structural, not catastrophic.",
    "file_placement": "Specifies which directory a class of files must live under; derived from `architecture_rules.file_placement_rules`.",
    "naming_convention": "Specifies a file or identifier naming pattern; typically expressible as a basename regex.",
    "infrastructure": "Build, CI, deploy, secrets, dependency-registry, signing conventions; lives in `azure-pipelines.yml`, `.github/`, `Dockerfile`, `package.json`, `pyproject.toml`, etc.",
    "coding_practice": "General project-specific guidance the agent should remember at edit time; catch-all when no narrower kind fits.",
}


def is_valid_kind(value: object) -> bool:
    """True iff value is one of the canonical kind strings (case-sensitive)."""
    return isinstance(value, str) and value in KINDS
