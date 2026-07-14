"""Lane-1 universal specialist lenses: four focused, blueprint-free bug hunts over
the diff + evidence pack. Each is a cheap haiku pass; findings flow through the
same gate as behavioral. Blind to intent-conformance beyond the shared brief."""
from __future__ import annotations
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from agent_cli import run_verifier  # noqa: E402
from behavioral_review import parse_findings  # noqa: E402

LENSES = [
    ("null-safety", "null-safety and error handling: null/None dereferences, "
                    "unhandled exceptions, silently-swallowed errors, wrong-result paths"),
    ("security", "security: injection, secrets in code, missing authz/authn, unsafe "
                 "deserialization, path traversal"),
    ("resource-perf", "resource & performance: N+1 queries, unbounded growth, leaked "
                      "handles/connections, missing pagination, accidental O(n^2)"),
    ("concurrency", "concurrency & state: races, shared mutable state, non-atomic "
                    "read-modify-write, ordering assumptions"),
]


def _prompt(diff_text, evidence, intent, focus):
    _pp = str(Path(__file__).parent)
    if _pp not in sys.path:
        sys.path.insert(0, _pp)
    from intent import intent_brief  # noqa: E402
    brief = intent_brief(intent) if intent else ""
    pre = (f"INTENDED CHANGE (context, not the review target):\n{brief}\n\n" if brief else "")
    ctx = f"\n\n{evidence}" if evidence else ""
    return (
        pre
        + f"You are a code reviewer focused ONLY on {focus}. Report only issues in "
        "this category INTRODUCED or worsened by the diff. Give a falsification test "
        "and anchor each to a changed line. Return JSON {\"findings\":[{"
        "\"problem_statement\":...,\"file\":...,\"line\":...,\"evidence\":[...],"
        "\"falsification\":...,\"confidence\":0.0,\"kind\":\"behavioral_break\"}]}."
        f"\n\nDIFF:\n{diff_text}{ctx}"
    )


def review_one(root, diff_text, evidence, intent, lens, run=None) -> list:
    if run is None:
        run = run_verifier
    key, focus = lens
    raw = run(_prompt(diff_text, evidence, intent, focus), Path(root), "claude")
    out = parse_findings(raw or "")
    for f in out:
        f["source"] = f"universal:{key}"
    return out


def review_universal(root, diff_text, evidence, intent, run=None) -> list:
    out = []
    for lens in LENSES:
        out += review_one(root, diff_text, evidence, intent, lens, run=run)
    return out
