"""Shared review brain: evidence pack -> parallel fan-out -> merge. One core for
both the CI delivery review and the local sync review (F3). Returns merged raw
findings pre-gate; the caller runs editor_gate + verdict."""
from __future__ import annotations
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from evidence_pack import build_pack             # noqa: E402
from behavioral_review import review as behavioral_review_run  # noqa: E402
import universal_specialists as us               # noqa: E402
from reconcile import review_conformance  # noqa: E402
from invariant_specialist import review_invariants  # noqa: E402
from selector import touched_context             # noqa: E402
from finding_merge import merge                  # noqa: E402


def _safe(t, stats=None):
    """Run a reviewer thunk; a raising reviewer degrades to no findings rather
    than crashing the whole fan-out. Used by both the serial and threaded paths.

    A failure is LOGGED and COUNTED. Swallowing it silently made a reviewer that
    timed out indistinguishable from one that found nothing — the same fail-open
    class as a hollow green verdict, one layer down.
    """
    try:
        out = t()
        if stats is not None:
            stats["total"] = stats.get("total", 0) + 1
        return out
    except Exception as e:
        if stats is not None:
            stats["total"] = stats.get("total", 0) + 1
            stats["failed"] = stats.get("failed", 0) + 1
        print(f"[archie] reviewer failed ({type(e).__name__}: {e})")
        return []


def _pmap(thunks, workers, stats=None):
    if workers <= 1:
        return [_safe(t, stats) for t in thunks]
    out = [None] * len(thunks)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_safe, t, stats): i for i, t in enumerate(thunks)}
        for fut, i in futs.items():
            out[i] = fut.result()
    return out


def run_review(root, diff_text, changed_files, blueprint, import_graph, spec,
               run=None, passes=1, workers=4, stats=None) -> list:
    passes = int(os.environ.get("ARCHIE_REVIEW_PASSES", passes))
    workers = int(os.environ.get("ARCHIE_REVIEW_WORKERS", workers))
    # Context prep must DEGRADE, never kill the fan-out: a shape quirk in one
    # blueprint took down every reviewer on both surfaces (SubscriberAgent PR #17
    # rendered a hollow green verdict). Reviewers run with less context instead.
    try:
        evidence = build_pack(root, changed_files, import_graph, blueprint)
    except Exception:
        evidence = ""
    try:
        ctx = touched_context(blueprint, changed_files)
    except Exception:
        ctx = {"invariants": [], "decisions": []}
    # Laws the user already retired at the confirm prompt: never pay Opus to
    # rediscover them. (Belt-and-braces — override-ack also stamps the blueprint
    # invariant `overridden`, and selector already drops dead-status invariants.)
    try:
        from contract_delta import acked_rule_ids
        _skip = acked_rule_ids(root)
    except Exception:
        _skip = frozenset()

    thunks = [
        lambda: behavioral_review_run(root, diff_text, import_graph, changed_files,
                                      run=run, intent=spec, evidence=evidence, passes=passes),
    ]
    for lens in us.LENSES:
        thunks.append(lambda lens=lens: us.review_one(root, diff_text, evidence, spec, lens, run=run))
    if ctx["invariants"]:
        thunks.append(lambda: review_invariants(root, diff_text, ctx["invariants"],
                                                run=run, skip_ids=_skip))
    if ctx["decisions"]:
        thunks.append(lambda: review_conformance(root, diff_text, [], ctx["decisions"],
                      run=run, intent=spec))

    if stats is not None:
        stats.setdefault("total", 0)
        stats.setdefault("failed", 0)

    raw = []
    for group in _pmap(thunks, workers, stats):
        raw += (group or [])
    if stats and stats.get("failed"):
        print(f"[archie] {stats['failed']} of {stats['total']} reviewers failed")
    return merge(raw, passes=passes)
