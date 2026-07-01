"""PR-gate delivery review: intake + full A/B/C reconciliation + verdict comment.
Reuses intent_review.post_or_update_comment for the upsert. Diffing, intent, and
gating come from the shared core.
"""
from __future__ import annotations

_OVERRIDE_LABEL = "archie-review"
_SKIP_LABEL = "archie-skip"


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
    labels = pr_meta.get("labels", []) or []
    if _OVERRIDE_LABEL in labels:
        return True, "override label"
    if str(pr_meta.get("author", "")).endswith("[bot]"):
        return False, "bot author"
    if _SKIP_LABEL in labels:
        return False, "skip label"
    if int(pr_meta.get("changed_files", 0)) > max_files:
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
            a = f.get("anchor", {})
            lines.append(f"- `{f.get('kind')}` {f.get('problem_statement', '')} "
                         f"({a.get('file', '')}:{a.get('line', '')})")
    return "\n".join(lines)


if __name__ == "__main__":
    # Full PR-gate orchestration (resolve_intent -> reconcile -> gate -> publish)
    # is not wired yet. This entrypoint is a deliberate placeholder.
    print("[archie] delivery-review: intake+verdict library ready; PR-gate orchestration pending.")
