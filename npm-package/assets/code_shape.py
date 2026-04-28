"""Code-shape matching primitives (Phase 2 of the richer-rules plan).

A `code_shape` entry is a small JSON object that the AI rule synthesizer
(Step 6 of /archie-deep-scan, Step 4 of /archie-scan) emits alongside a
rule. The pre-validate hook + the index builder consume these entries to
narrow candidate rules at edit time without parsing the full rule set
on every keystroke.

The shape DSL is deliberately small and regex-based — no tree-sitter
dependency. The AI writes regexes that capture the structural pattern
(function signature, import, content marker). Most architectural
violations have a regex-shaped tell at the line/file level; the ones
that don't are deferred to the plan/commit-time classifier (Phase 3).

Shape kinds:
    {
        "kind": "regex_in_content",
        "must_match": ["pattern1", ...],     # at least one must match
        "must_not_match": ["pattern2", ...],  # none may match
    }

`must_match` and `must_not_match` accept either a single string or an
array of strings. An empty array means "no constraint" (skipped).

Path globbing supports * (within a segment) and ** (across segments).
Mirrors the matcher in check_rules.py so behavior is consistent.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


def _coerce_list(value: Any) -> list[str]:
    """Return value as a list of strings; accept str | list | None."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []


def _any_regex_matches(patterns: Iterable[str], text: str) -> bool:
    for p in patterns:
        try:
            if re.search(p, text):
                return True
        except re.error:
            continue
    return False


def matches_code_shape(content: str, shape: dict[str, Any]) -> bool:
    """Return True iff `content` matches the given shape.

    Empty / malformed shapes return False — a shape that says "no
    constraint at all" doesn't fire. The AI must emit at least one
    must_match pattern for a shape to be meaningful.
    """
    if not isinstance(shape, dict):
        return False
    kind = shape.get("kind", "regex_in_content")
    if kind != "regex_in_content":
        # Unknown kinds are ignored (forward compat — future kinds added
        # without breaking older hooks)
        return False

    must_match = _coerce_list(shape.get("must_match"))
    must_not = _coerce_list(shape.get("must_not_match"))

    if not must_match:
        return False  # no positive trigger -> never fires

    if not _any_regex_matches(must_match, content):
        return False
    if must_not and _any_regex_matches(must_not, content):
        return False
    return True


def matches_path_glob(rel_path: str, pattern: str) -> bool:
    """Match a relative path against a glob pattern.

    Supports:
        *         — matches anything within a single path segment (no /)
        **        — matches any number of path segments (including zero)
        a/**/b    — matches a/b AND a/x/b AND a/x/y/b ...
        a/**$     — matches a, a/x, a/x/y ...
        ^**/b     — matches b AND x/b AND x/y/b ...
        a/        — directory-prefix shorthand: a, a/anything

    Empty pattern matches nothing. Callers should guard.
    """
    if not pattern:
        return False
    # Directory-prefix shorthand: "src/api/" matches src/api or anything under it
    if pattern.endswith("/") and "*" not in pattern:
        return rel_path.startswith(pattern) or rel_path == pattern.rstrip("/")

    # Build the regex one piece at a time to handle ** correctly
    # (re.escape escapes too aggressively, so we walk char-by-char).
    out: list[str] = ["^"]
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            # Detect ** (greedy, multi-segment)
            if i + 1 < n and pattern[i + 1] == "*":
                # Look at neighbors to decide the right zero-segment-or-more pattern
                left_slash = i > 0 and pattern[i - 1] == "/"
                right_slash = i + 2 < n and pattern[i + 2] == "/"
                if left_slash and right_slash:
                    # `a/**/b` — pop the trailing "/" we already emitted, emit "(?:/.*)?/"
                    out[-1] = "(?:/.*)?/"
                    i += 3  # skip ** and the following /
                    continue
                if right_slash:
                    # `**/b` at start — emit "(?:.*/)?"
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                if left_slash:
                    # `a/**` at end — pop the "/" and emit "(?:/.*)?"
                    out[-1] = "(?:/.*)?"
                    i += 2
                    continue
                # Bare ** (no surrounding /) — match anything across segments
                out.append(".*")
                i += 2
                continue
            # Single * — anything within a segment
            out.append("[^/]*")
            i += 1
            continue
        # Escape regex metacharacters; keep / literal
        if c in r".+?^$()[]{}|\\":
            out.append("\\" + c)
        else:
            out.append(c)
        i += 1
    out.append("$")
    regex = "".join(out)
    try:
        return bool(re.match(regex, rel_path))
    except re.error:
        return False


def any_path_glob_matches(rel_path: str, patterns: Iterable[str]) -> bool:
    """Return True iff any pattern in `patterns` matches `rel_path`."""
    for p in patterns:
        if matches_path_glob(rel_path, p):
            return True
    return False


def rule_triggers_match(
    rule: dict[str, Any],
    rel_path: str,
    content: str,
) -> bool:
    """Return True iff the rule's `triggers` block fires for the given edit.

    A rule's `triggers` block is optional. When absent, the rule is
    considered "always candidate" — old-shape rules without triggers
    keep firing under the existing path/check semantics. When present,
    BOTH path_glob (if specified) AND code_shape (if specified) must
    match for the rule to be considered a candidate.

    A rule with `triggers` but neither path_glob nor code_shape filled
    in is a legitimate "for_classifier" rule (Phase 3 only) — it
    matches nothing at edit time.
    """
    triggers = rule.get("triggers")
    if not isinstance(triggers, dict):
        return True  # no triggers block -> always candidate (legacy)

    path_globs = _coerce_list(triggers.get("path_glob"))
    code_shapes = triggers.get("code_shape") or []
    if not isinstance(code_shapes, list):
        code_shapes = []

    if not path_globs and not code_shapes:
        return False  # explicit empty triggers -> classifier-only rule

    if path_globs and not any_path_glob_matches(rel_path, path_globs):
        return False
    if code_shapes:
        if not any(matches_code_shape(content, s) for s in code_shapes):
            return False
    return True
