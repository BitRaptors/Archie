"""Enforcement logic -- extracted from hook scripts for testability."""

from __future__ import annotations

import os
import re


def check_pre_validate(file_path: str, rules: list[dict]) -> dict:
    """Check a file against enforcement rules.

    Implements the same validation logic as the Python code embedded in
    ``pre-validate.sh``: file-placement checks (``allowed_dirs``) and naming
    checks (``pattern`` regex against the basename).

    Returns ``{"pass": bool, "warnings": [...], "errors": [...]}``.
    """
    warnings: list[str] = []
    errors: list[str] = []
    filename = os.path.basename(file_path)

    for rule in rules:
        # The extractor writes "check"; the hook script historically used
        # "type".  Accept either key so the logic works regardless.
        rule_type = rule.get("check") or rule.get("type", "")
        severity = rule.get("severity", "warn")
        rid = rule.get("id", "unknown")
        desc = rule.get("description", "")

        # -- file_placement --------------------------------------------------
        if rule_type == "file_placement":
            allowed_dirs = rule.get("allowed_dirs", [])
            if allowed_dirs:
                matched = any(file_path.startswith(d) for d in allowed_dirs)
                if not matched:
                    msg = f"{rid}: {desc} (file: {file_path})"
                    if severity == "error":
                        errors.append(msg)
                    else:
                        warnings.append(msg)

        # -- naming -----------------------------------------------------------
        if rule_type == "naming":
            pattern = rule.get("pattern", "")
            if pattern:
                if not re.search(pattern, filename):
                    msg = f"{rid}: {desc} (file: {file_path})"
                    if severity == "error":
                        errors.append(msg)
                    else:
                        warnings.append(msg)

    return {
        "pass": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
    }


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

        # Always include error-severity rules.
        if rule.get("severity") == "error":
            if rid not in seen_ids:
                seen_ids.add(rid)
                matched.append(rule)
            continue

        # Keyword match.
        keywords = rule.get("keywords", [])
        found = False
        for kw in keywords:
            if kw.lower() in prompt_lower:
                found = True
                break

        # Token-from-text match.
        if not found:
            rule_text = (rule.get("id", "") + " " + rule.get("description", "")).lower()
            tokens = rule_text.split()
            for token in tokens:
                if len(token) > 3 and token in prompt_lower:
                    found = True
                    break

        if found and rid not in seen_ids:
            seen_ids.add(rid)
            matched.append(rule)

    return matched
