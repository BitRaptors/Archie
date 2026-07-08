"""The delivery review was silently overwriting the intent review's comment.

Proven in the SubscriberAgent PR #17 run log:

    [intent-review] posted new comment              <- intent_review posts
    [intent-review] updated comment 4913709782      <- delivery_review PATCHes over it

Both scripts looked comments up by `intent_review.COMMENT_MARKER`, so delivery ate
intent's comment on every run — leaking one orphaned comment per run, and intent's
judgment was never visible on a PR.
"""
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent_review as ir  # noqa: E402

COMMENTS = [
    {"id": 1, "body": "<!-- archie-intent-review -->\nintent stuff"},
    {"id": 2, "body": "<!-- archie-delivery-review -->\ndelivery stuff"},
]


def test_finds_comment_by_its_own_marker(monkeypatch):
    monkeypatch.setattr(ir, "_gh_request", lambda *a, **k: (COMMENTS, None))
    assert ir._find_existing_comment_id("o", "r", 1, "t") == 1                  # default
    assert ir._find_existing_comment_id("o", "r", 1, "t",
                                        marker="<!-- archie-delivery-review -->") == 2


def test_delivery_marker_never_matches_intent_comment(monkeypatch):
    monkeypatch.setattr(ir, "_gh_request", lambda *a, **k: ([COMMENTS[0]], None))
    assert ir._find_existing_comment_id(
        "o", "r", 1, "t", marker="<!-- archie-delivery-review -->") is None


def test_post_or_update_threads_the_marker(monkeypatch):
    seen = {}

    def fake_find(o, r, n, t, marker=ir.COMMENT_MARKER):
        seen["marker"] = marker
        return None

    monkeypatch.setattr(ir, "_find_existing_comment_id", fake_find)
    monkeypatch.setattr(ir, "_gh_request", lambda *a, **k: (None, None))
    ir.post_or_update_comment("o", "r", 1, "body", "t",
                              marker="<!-- archie-delivery-review -->")
    assert seen["marker"] == "<!-- archie-delivery-review -->"


def test_safe_post_comment_threads_the_marker(monkeypatch):
    seen = {}
    monkeypatch.setattr(ir, "post_or_update_comment",
                        lambda o, r, n, b, t, marker=ir.COMMENT_MARKER: seen.update(marker=marker))
    ir.safe_post_comment("o", "r", 1, "body", "tok", marker="<!-- archie-delivery-review -->")
    assert seen["marker"] == "<!-- archie-delivery-review -->"


def test_delivery_review_posts_with_its_own_marker():
    """The body's marker and the lookup marker must be the same string."""
    sys.path.insert(0, str(_STANDALONE))
    import delivery_review as dr
    assert dr.DELIVERY_MARKER == "<!-- archie-delivery-review -->"
    body = dr.render_verdict({"breaks": 0}, [], {})
    assert body.startswith(dr.DELIVERY_MARKER)


def test_workflow_runs_one_review_step():
    wf = (Path(__file__).resolve().parent.parent / "archie" / "assets" /
          "workflows" / "archie-intent-review.yml").read_text()
    assert "intent_review.py" not in wf          # judgment now lives in the delivery comment
    assert wf.count("delivery_review.py") >= 1
