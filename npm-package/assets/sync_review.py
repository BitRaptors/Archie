"""Sync-surface delivery review: continuous, non-blocking. Runs the SAME shared
review core as the CI delivery review (F3) on the branch delta — evidence pack +
parallel fan-out (edge A, behavioral, four universal lenses, edge C, and the
tracer/challenger invariant specialist + conformance for touched blueprint items)
— then gates and returns a status-line verdict.

SKIP-GATE: if select_specialists picks no specialists AND no changed file is
source code, returns {"skipped": True} without any LLM call (the fast no-op path
is preserved even though the fan-out itself is now the full core).

Import convention: bare-name imports via sys.path so this works on Python 3.9
(archie/__init__.py uses tomllib which is 3.11+).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from _common import SOURCE_EXTENSIONS                      # noqa: E402
from agent_cli import run_verifier                         # noqa: E402
from selector import select_specialists, touched_context   # noqa: E402
from intent import load_branch_record, normalize, save_branch_record, load_committed_intent  # noqa: E402
from reconcile import review_edge_a, review_edge_c, aggregate_verdict, review_conformance   # noqa: E402
from behavioral_review import review as behavioral_review_run   # noqa: E402
from editor_gate import gate                               # noqa: E402


def _is_source(f: str) -> bool:
    """Return True if f has a source-code extension."""
    return any(f.endswith(ext) for ext in SOURCE_EXTENSIONS)


def run_sync_review(
    root,
    branch,
    blueprint,
    import_graph,
    diff_text,
    changed_files,
    changed_lines,
    floors,
    *,
    run=None,
) -> dict:
    """Run a light sync delivery review on the branch delta.

    Args:
        root: Path to the project root (str or Path).
        branch: Current branch name.
        blueprint: Blueprint dict (from blueprint.json).
        import_graph: Import graph dict for blast-radius computation.
        diff_text: Unified diff text for the branch delta.
        changed_files: List of changed file paths (relative to root).
        changed_lines: Dict mapping file paths to sets of changed line numbers.
        floors: Dict mapping finding kind -> minimum confidence threshold.
        run: LLM runner (injected for testing; defaults to run_verifier at
             call time so monkeypatching works).

    Returns:
        dict with keys:
        - skipped: True if the skip-gate fired (no source files, no specialists).
        - confirmed: list of confirmed findings, acked ones excluded (absent when skipped).
        - acked: list of (override_entry, [findings]) pairs for acked rule_ids
          (absent when skipped) — see delivery_review.partition_for_verdict.
        - stale_acks: list of override entries whose acked rule_id had no
          matching finding this run (absent when skipped).
        - verdict: aggregate_verdict dict computed over confirmed only (absent when skipped).
    """
    if run is None:
        run = run_verifier   # call-time lookup — monkeypatch takes effect

    # SKIP-GATE: no specialists AND no source code touched → no LLM call
    sel = select_specialists(blueprint, changed_files)
    if not sel["specialists"] and not any(_is_source(f) for f in changed_files):
        return {"skipped": True}

    # Load or synthesize intent spec for this branch
    archie_dir = Path(root) / ".archie"
    spec = (load_committed_intent(root)
            or load_branch_record(archie_dir, branch)
            or normalize("", source="inferred", ticket_ids=[]))

    # Resolve acceptance_criteria from raw text when not yet populated
    if not spec.get("acceptance_criteria") and spec.get("raw"):
        try:
            from intent import resolve
            spec = resolve(spec, run=run)
            # Persist the resolved spec so the LLM call isn't repeated every
            # sync — only when resolve actually populated acceptance_criteria.
            if spec.get("acceptance_criteria"):
                try:
                    save_branch_record(archie_dir, branch, spec)
                except Exception:
                    pass
        except Exception:
            pass

    # Run the reviewers via the shared core (evidence pack + parallel fan-out + merge) —
    # the SAME brain the CI delivery review uses (F3). Import inside the function so a
    # test can monkeypatch review_core.run_review. Guarded like the CI surface: a core
    # failure degrades to no findings rather than aborting the sync review.
    raw = []
    try:
        from review_core import run_review
        raw = run_review(root, diff_text, changed_files, blueprint, import_graph, spec, run=run)
    except Exception:
        pass

    # Load existing findings store for dedup
    store: list[dict] = []
    fp = archie_dir / "findings.json"
    if fp.exists():
        try:
            store = json.loads(fp.read_text()).get("findings", [])
        except Exception:
            store = []

    # Gate: validate, floor-check, anchor-check, dedup
    result = gate(raw, store, changed_lines=changed_lines, floors=floors)

    # Human rulings: acked overrides are surfaced, not counted — the SAME
    # partition the CI delivery review uses (one join for both surfaces).
    from delivery_review import partition_for_verdict
    confirmed, acked, stale_acks = partition_for_verdict(root, result["confirmed"])

    return {
        "skipped": False,
        "confirmed": confirmed,
        "acked": acked,
        "stale_acks": stale_acks,
        "verdict": aggregate_verdict(spec, confirmed),
    }
