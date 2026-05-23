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


import re  # noqa: E402 — placed after module-level constants intentionally

# id prefix → kind. Order matters only for documentation; lookup is O(1).
_ID_PREFIX_TO_KIND: dict[str, str] = {
    "layer": "layering",
    "naming": "naming_convention",
    "placement": "file_placement",
    "pitfall": "pitfall",
    "chain": "decision",
    "tradeoff": "tradeoff",
    "pattern": "semantic_pattern",
    "extend": "semantic_pattern",
    "scope": "semantic_pattern",
    "impact": "decision",
    "arch": "decision",
    "dep": "decision",
}

# severity_class → kind fallback.
_SEVERITY_CLASS_TO_KIND: dict[str, str] = {
    "decision_violation": "decision",
    "pitfall_triggered": "pitfall",
    "tradeoff_undermined": "tradeoff",
    # pattern_divergence and mechanical_violation are too generic to map.
}

# check field → kind fallback.
_CHECK_TO_KIND: dict[str, str] = {
    "file_naming": "naming_convention",
    "forbidden_import": "layering",
    "architectural_constraint": "layering",
    # forbidden_content, required_pattern → too generic, no mapping.
}

# Infrastructure paths — substring match on `source` / `applies_to` / `file_pattern`.
_INFRA_PATH_MARKERS: tuple[str, ...] = (
    "azure-pipelines",
    "dockerfile",
    ".github/",
    ".gitlab-ci",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "cargo.toml",
    "go.mod",
    "build.gradle",
    "gemfile",
    "entitlements",
    ".env.example",
)

_ID_PREFIX_RE = re.compile(r"^([a-z]+)[-_]?\d", re.IGNORECASE)


def _id_prefix(rule_id: object) -> str | None:
    if not isinstance(rule_id, str):
        return None
    m = _ID_PREFIX_RE.match(rule_id)
    return m.group(1).lower() if m else None


def _looks_like_infra_path(value: object) -> bool:
    if not isinstance(value, str):
        return False
    low = value.lower()
    return any(marker in low for marker in _INFRA_PATH_MARKERS)


def classify_kind(rule: dict) -> str:
    """Pick the best `kind` for a rule using a priority chain.

    Priority (first match wins):
      1. Existing valid `kind` field — preserve user/AI work.
      2. id prefix (most specific signal).
      3. severity_class (when it implies kind unambiguously).
      4. Structural fields (forbidden_imports, allowed_dirs, check).
      5. Infrastructure path markers on source/applies_to/file_pattern.
      6. Fallback: coding_practice.
    """
    existing = rule.get("kind")
    if is_valid_kind(existing):
        return existing  # type: ignore[return-value]

    prefix = _id_prefix(rule.get("id"))
    if prefix and prefix in _ID_PREFIX_TO_KIND:
        return _ID_PREFIX_TO_KIND[prefix]

    sev = rule.get("severity_class")
    if isinstance(sev, str) and sev in _SEVERITY_CLASS_TO_KIND:
        return _SEVERITY_CLASS_TO_KIND[sev]

    if isinstance(rule.get("forbidden_imports"), list) and rule["forbidden_imports"]:
        return "layering"
    if isinstance(rule.get("allowed_dirs"), list) and rule["allowed_dirs"]:
        return "file_placement"

    check = rule.get("check")
    if isinstance(check, str) and check in _CHECK_TO_KIND:
        return _CHECK_TO_KIND[check]

    if isinstance(rule.get("pattern_name"), str):
        return "semantic_pattern"

    if isinstance(rule.get("violation_signals"), list):
        return "tradeoff"

    # Path-based infrastructure detection.
    for field in ("source", "applies_to", "file_pattern", "location"):
        if _looks_like_infra_path(rule.get(field)):
            return "infrastructure"

    return "coding_practice"
