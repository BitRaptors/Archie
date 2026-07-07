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
from reconcile import review_edge_a, review_edge_c, review_conformance  # noqa: E402
from invariant_specialist import review_invariants  # noqa: E402
from selector import touched_context             # noqa: E402
from finding_merge import merge                  # noqa: E402


def _safe(t):
    """Run a reviewer thunk; a raising reviewer degrades to no findings rather
    than crashing the whole fan-out. Used by both the serial and threaded paths."""
    try:
        return t()
    except Exception:
        return []


def _pmap(thunks, workers):
    if workers <= 1:
        return [_safe(t) for t in thunks]
    out = [None] * len(thunks)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_safe, t): i for i, t in enumerate(thunks)}
        for fut, i in futs.items():
            out[i] = fut.result()
    return out


def run_review(root, diff_text, changed_files, blueprint, import_graph, spec,
               run=None, passes=2, workers=4) -> list:
    passes = int(os.environ.get("ARCHIE_REVIEW_PASSES", passes))
    workers = int(os.environ.get("ARCHIE_REVIEW_WORKERS", workers))
    evidence = build_pack(root, changed_files, import_graph, blueprint)
    ctx = touched_context(blueprint, changed_files)
    has_intent = bool(spec.get("acceptance_criteria") or spec.get("goals"))

    thunks = [
        lambda: review_edge_a(root, spec, diff_text, run=run),
        lambda: behavioral_review_run(root, diff_text, import_graph, changed_files,
                                      run=run, intent=spec, evidence=evidence, passes=passes),
    ]
    for lens in us.LENSES:
        thunks.append(lambda lens=lens: us.review_one(root, diff_text, evidence, spec, lens, run=run))
    if has_intent:
        live_invariants = [i for i in (blueprint.get("domain_invariants") or [])
                          if i.get("status") not in ("overridden", "override_staged")]
        thunks.append(lambda: review_edge_c(root, spec, live_invariants, run=run))
    if ctx["invariants"]:
        thunks.append(lambda: review_invariants(root, diff_text, ctx["invariants"], run=run))
    if ctx["decisions"]:
        thunks.append(lambda: review_conformance(root, diff_text, [], ctx["decisions"],
                      run=run, intent=spec))

    raw = []
    for group in _pmap(thunks, workers):
        raw += (group or [])
    return merge(raw, passes=passes)
