"""PR-gate delivery review: intake + full A/B/C reconciliation + verdict comment.
Reuses intent_review.post_or_update_comment for the upsert. Diffing, intent, and
gating come from the shared core.
"""
from __future__ import annotations

import html

_OVERRIDE_LABEL = "archie-review"
_SKIP_LABEL = "archie-skip"

# Zero-width space used to neutralize leading @ in model-derived text.
_ZWS = "​"


def _sanitize(text: object) -> str:
    """Sanitize a model-derived field before embedding in a Markdown comment.

    - Coerces to str.
    - HTML-escapes <, >, & so injected HTML comment markers (<!--/-->) become
      harmless entities (&lt;!-- / --&gt;) and raw HTML tags are neutralized.
    - Neutralizes leading @ on any whitespace-separated token to prevent live
      GitHub @mention notifications.
    """
    s = html.escape(str(text) if text is not None else "")
    # Neutralize @ mentions: replace bare @ at word boundaries.
    tokens = s.split(" ")
    sanitized_tokens = []
    for tok in tokens:
        if tok.startswith("@"):
            tok = "@" + _ZWS + tok[1:]
        sanitized_tokens.append(tok)
    return " ".join(sanitized_tokens)


def should_review(pr_meta: dict, max_files: int) -> tuple[bool, str]:
    """Determine if a PR should receive a delivery review.

    Returns (eligible: bool, reason: str).

    Priority order:
    1. Override label forces True even for bots.
    2. Bot author → False.
    3. Skip label → False.
    4. Too many changed files → False.
    5. Otherwise → True.
    """
    labels = pr_meta.get("labels") or []
    if _OVERRIDE_LABEL in labels:
        return True, "override label"
    if str(pr_meta.get("author", "")).endswith("[bot]"):
        return False, "bot author"
    if _SKIP_LABEL in labels:
        return False, "skip label"
    if int(pr_meta.get("changed_files") or 0) > max_files:
        return False, "too many files"
    return True, "eligible"


def render_verdict(verdict: dict, confirmed: list[dict]) -> str:
    """Render a Markdown delivery verdict comment.

    Args:
        verdict: dict with keys intent_completeness, breaks, conflicts.
        confirmed: list of confirmed finding dicts with kind, problem_statement, anchor.

    Returns:
        Markdown string with HTML marker comment for upsert.
    """
    lines = ["<!-- archie-delivery-review -->", "## Delivery review", ""]
    lines.append(f"**Built the intent?** {verdict.get('intent_completeness', '?')} acceptance criteria.")
    lines.append(f"**Broke anything?** {verdict.get('breaks', 0)} break(s), "
                 f"{verdict.get('conflicts', 0)} requirement conflict(s).")
    if confirmed:
        lines.append("")
        for f in confirmed:
            a = f.get("anchor", {}) or {}
            kind = _sanitize(f.get("kind", ""))
            problem = _sanitize(f.get("problem_statement", ""))
            anchor_file = _sanitize(a.get("file", ""))
            anchor_line = int(a.get("line") or 0) if a.get("line") is not None else ""
            lines.append(f"- `{kind}` {problem} "
                         f"({anchor_file}:{anchor_line})")
    return "\n".join(lines)


if __name__ == "__main__":
    # Full PR-gate orchestration (resolve_intent -> reconcile -> gate -> publish)
    # is not wired yet. This entrypoint is a deliberate placeholder.
    print("[archie] delivery-review: intake+verdict library ready; PR-gate orchestration pending.")
