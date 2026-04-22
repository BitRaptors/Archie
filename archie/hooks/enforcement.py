"""Enforcement logic -- extracted from hook scripts for testability.

This module mirrors the validation logic embedded in the standalone
``install_hooks.py`` PRE_VALIDATE_HOOK so it can be unit-tested without
shelling out. Keep the two in sync: the standalone hook is the runtime
contract agents see; this module is the code path ``archie init`` uses and
the test suite exercises.

Supported check types:
    file_placement          — directory prefix allow-list on file path
    naming                  — regex match on basename
    file_naming             — regex match scoped by ``applies_to`` glob
    forbidden_import        — regex on content, scoped by ``applies_to`` prefix
    forbidden_content       — regex on content, optionally scoped
    required_pattern        — content must contain one of ``required_in_content``
    architectural_constraint — regex on content, scoped by ``file_pattern`` glob
"""

from __future__ import annotations

import fnmatch
import os
import re


def check_pre_validate(
    file_path: str,
    rules: list[dict],
    content: str = "",
    project_root: str = "",
) -> dict:
    """Check a file (and optionally its new content) against enforcement rules.

    Args:
        file_path: Absolute or relative path to the file being written.
        rules: List of rule dicts loaded from rules.json / platform_rules.json.
        content: The new content being written (Write.content / Edit.new_string).
            When empty, content-based rules (forbidden_*, required_*,
            architectural_constraint) are skipped — fail open.
        project_root: Absolute project root; used to compute a relative path
            for ``applies_to`` prefix matching. If empty, ``file_path`` is used
            as-is for the relative check.

    Returns ``{"pass": bool, "warnings": [...], "errors": [...]}``.
    """
    warnings: list[str] = []
    errors: list[str] = []
    filename = os.path.basename(file_path)

    if project_root and file_path.startswith(project_root):
        rel_path = file_path[len(project_root):].lstrip("/")
    else:
        rel_path = file_path

    for rule in rules:
        # Accept either "check" (new) or "type" (legacy) key.
        rule_type = rule.get("check") or rule.get("type", "")
        severity = rule.get("severity", "warn")
        rid = rule.get("id", "unknown")
        desc = rule.get("description", "")
        msg = f"{rid}: {desc} (file: {file_path})"
        bucket = errors if severity == "error" else warnings

        if rule_type == "file_placement":
            allowed_dirs = rule.get("allowed_dirs", [])
            if allowed_dirs and not any(file_path.startswith(d) for d in allowed_dirs):
                bucket.append(msg)

        elif rule_type == "naming":
            pattern = rule.get("pattern", "")
            if pattern and not re.search(pattern, filename):
                bucket.append(msg)

        elif rule_type == "file_naming":
            applies_to = rule.get("applies_to", "")
            file_pattern = rule.get("file_pattern", "")
            if applies_to and fnmatch.fnmatch(rel_path, applies_to) and file_pattern:
                try:
                    if not re.match(file_pattern, filename):
                        bucket.append(msg)
                except re.error:
                    pass

        elif rule_type == "forbidden_import":
            applies_to = rule.get("applies_to", "")
            if applies_to and rel_path.startswith(applies_to) and content:
                if _any_pattern_matches(rule.get("forbidden_patterns", []), content):
                    bucket.append(msg)

        elif rule_type == "forbidden_content":
            applies_to = rule.get("applies_to", "")
            if content and (not applies_to or rel_path.startswith(applies_to)):
                if _any_pattern_matches(rule.get("forbidden_patterns", []), content):
                    bucket.append(msg)

        elif rule_type == "required_pattern":
            file_pattern = rule.get("file_pattern", "")
            if file_pattern and fnmatch.fnmatch(filename, file_pattern) and content:
                required = rule.get("required_in_content", [])
                if required and not any(req in content for req in required):
                    bucket.append(msg)

        elif rule_type == "architectural_constraint":
            file_pattern = rule.get("file_pattern", "")
            if file_pattern and fnmatch.fnmatch(filename, file_pattern) and content:
                if _any_pattern_matches(rule.get("forbidden_patterns", []), content):
                    bucket.append(msg)

    return {
        "pass": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
    }


def rules_to_inject(
    file_path: str,
    rules: list[dict],
    already_injected_ids: set[str] | list[str] | None = None,
    project_root: str = "",
) -> list[dict]:
    """Return rules that should be surfaced to the agent before an edit.

    A rule is eligible for injection when:
    - It is path-scoped (``applies_to`` non-empty) AND the file's rel_path
      starts with that prefix, OR
    - It is tagged ``always_inject: true`` (a critical global the user wants
      re-surfaced even though it's also in CLAUDE.md).

    Rules whose ``id`` is in ``already_injected_ids`` are filtered out so the
    same rule doesn't re-inject on every Edit within a turn. The caller is
    responsible for persisting the set (typically a /tmp marker cleared on
    UserPromptSubmit).
    """
    seen = set(already_injected_ids or [])

    rel_path = file_path
    if project_root and file_path.startswith(project_root):
        rel_path = file_path[len(project_root):].lstrip("/")

    out: list[dict] = []
    for rule in rules:
        rid = rule.get("id", "")
        if not rid or rid in seen:
            continue

        applies_to = rule.get("applies_to", "")
        always = bool(rule.get("always_inject"))
        path_match = bool(applies_to) and rel_path.startswith(applies_to)

        if always or path_match:
            out.append(rule)
            seen.add(rid)

    return out


def _any_pattern_matches(patterns: list[str], content: str) -> bool:
    """Return True if any of the regex patterns matches the content.

    Invalid regexes are silently skipped so one broken rule can't sink the hook.
    """
    for pat in patterns:
        try:
            if re.search(pat, content):
                return True
        except re.error:
            continue
    return False


def match_context_rules(prompt: str, rules: list[dict]) -> list[dict]:
    """Match user prompt against rules by keyword overlap.

    Returns list of matched rules.  All rules with ``severity == "error"``
    are always included regardless of keyword matches.  For other rules a
    match occurs when:

    1. Any of the rule's explicit ``keywords`` appear in the prompt, **or**
    2. Any token (length > 3) extracted from ``id + description`` appears in
       the lowered prompt.
    """
    prompt_lower = prompt.lower()
    matched: list[dict] = []
    seen_ids: set[str] = set()

    for rule in rules:
        rid = rule.get("id", "unknown")

        if rule.get("severity") == "error":
            if rid not in seen_ids:
                seen_ids.add(rid)
                matched.append(rule)
            continue

        keywords = rule.get("keywords", [])
        found = any(kw.lower() in prompt_lower for kw in keywords)

        if not found:
            rule_text = (rule.get("id", "") + " " + rule.get("description", "")).lower()
            for token in rule_text.split():
                if len(token) > 3 and token in prompt_lower:
                    found = True
                    break

        if found and rid not in seen_ids:
            seen_ids.add(rid)
            matched.append(rule)

    return matched
