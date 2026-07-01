"""End-to-end pipeline integration test: drives REAL modules composed together.

Only `run_verifier` (the LLM seam) is mocked — all real module wiring runs:
selector → intent.save_branch_record → intent.resolve → review_edge_a
→ behavioral_review → review_edge_c → editor_gate → aggregate_verdict.

Import convention: bare sys.path insert, then bare module imports.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import sync_review  # noqa: E402
import intent       # noqa: E402

# ---------------------------------------------------------------------------
# Shared blueprint with one domain invariant citing billing/usage.py
# ---------------------------------------------------------------------------
BLUEPRINT = {
    "domain_invariants": [
        {
            "id": "inv-tenant-scope",
            "invariant": "All exports must be scoped to the requesting tenant.",
            "enforced_at": ["billing/usage.py:44"],
        }
    ],
    "data_models": [
        {"name": "UsageRecord", "location": "billing/usage.py"}
    ],
    "persistence_stores": [
        {"name": "usage_db", "location": "billing/usage.py"}
    ],
    "decisions": {"key_decisions": []},
}

CHANGED_FILES = ["billing/usage.py"]
CHANGED_LINES = {"billing/usage.py": {12, 44}}
IMPORT_GRAPH = {"billing/usage.py": [], "api/export.py": ["billing/usage.py"]}
DIFF_TEXT = "diff --git a/billing/usage.py\n+def export(tenant_id): ..."
BRANCH = "feature/ARCH-9-export"


def _make_fake_run():
    """Return a fake LLM runner that dispatches based on prompt content."""

    def fake_run(prompt: str, root, model: str) -> str:
        # resolve() — fills acceptance_criteria from raw text
        if "acceptance criteria" in prompt and "Extract the concrete" in prompt:
            return json.dumps({
                "goals": ["tenant-scoped export"],
                "acceptance_criteria": [
                    {"id": "ac1", "text": "export is tenant-scoped"},
                    {"id": "ac2", "text": "rate limited"},
                ],
            })

        # edge-A per-criterion check
        if "acceptance criterion" in prompt or ("CRITERIA:" in prompt and "DIFF:" in prompt):
            return json.dumps({
                "findings": [
                    {
                        "id": "f_a_1",
                        "criterion_id": "ac2",
                        "verdict": "unmet",
                        "file": "billing/usage.py",
                        "line": 44,
                        "evidence": ["no rate-limit header found in diff"],
                        "falsification": "Show a 429 response path in the diff",
                        "confidence": 0.8,
                    }
                ]
            })

        # behavioral review
        if "behavioral" in prompt or "BLAST RADIUS" in prompt:
            return json.dumps({
                "findings": [
                    {
                        "id": "f_beh_1",
                        "kind": "behavioral_break",
                        "problem_statement": "Export may leak cross-tenant data",
                        "file": "billing/usage.py",
                        "line": 12,
                        "assumptions": ["tenant_id not validated"],
                        "evidence": ["no tenant check in export()"],
                        "falsification": "Show tenant guard at line 12",
                        "confidence": 0.9,
                    }
                ]
            })

        # edge-C — requirement vs invariants
        if "VIOLATE any standing architectural invariant" in prompt:
            return json.dumps({"findings": []})

        return json.dumps({"findings": []})

    return fake_run


# ---------------------------------------------------------------------------
# Test 1: full composition
# ---------------------------------------------------------------------------
def test_integration_full_pipeline(tmp_path):
    """Drive ALL real modules together; only LLM is mocked.

    Proves: selector + resolve + edge-A + behavioral + edge-C + editor_gate
    + aggregate_verdict all compose without shape-mismatch errors.
    """
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()

    # Set up branch intent record with raw text and empty acceptance_criteria
    spec = intent.normalize(
        "Add tenant-scoped export; rate-limit to 10/min",
        source="prompt",
        ticket_ids=[],
    )
    intent.save_branch_record(archie_dir, BRANCH, spec)

    out = sync_review.run_sync_review(
        str(tmp_path),
        BRANCH,
        BLUEPRINT,
        IMPORT_GRAPH,
        DIFF_TEXT,
        CHANGED_FILES,
        CHANGED_LINES,
        floors={
            "behavioral_break": 0.5,
            "intent_unmet": 0.4,
            "intent_partial": 0.4,
            "intent_drift": 0.5,
        },
        run=_make_fake_run(),
    )

    # 1. Not skipped — billing/usage.py is source AND cites a domain invariant
    assert out["skipped"] is False, f"Expected not skipped, got: {out}"

    confirmed = out["confirmed"]
    confirmed_kinds = {f["kind"] for f in confirmed}
    confirmed_ids = {f["id"] for f in confirmed}

    # 2. intent_unmet (ac2/rate-limit) survived the gate — anchor line 44 is changed
    assert "intent_unmet" in confirmed_kinds, (
        f"Expected intent_unmet in confirmed kinds: {confirmed_kinds}\n"
        f"confirmed: {confirmed}"
    )

    # 3. behavioral_break survived the gate — anchor line 12 is changed
    assert "behavioral_break" in confirmed_kinds, (
        f"Expected behavioral_break in confirmed kinds: {confirmed_kinds}\n"
        f"confirmed: {confirmed}"
    )

    # 4. Both specific findings are present
    assert "f_a_1" in confirmed_ids or any(
        f.get("criterion_id") == "ac2" for f in confirmed
    ), f"ac2/rate-limit finding missing from confirmed: {confirmed}"

    assert "f_beh_1" in confirmed_ids or any(
        f.get("kind") == "behavioral_break" for f in confirmed
    ), f"behavioral finding missing from confirmed: {confirmed}"

    # 5. intent_completeness: resolve() gave 2 criteria; ac2 is unmet → "1/2"
    verdict = out["verdict"]
    assert verdict["intent_completeness"] == "1/2", (
        f"Expected '1/2' completeness (2 criteria, 1 unmet), got: {verdict['intent_completeness']}"
    )

    # 6. At least 1 break counted
    assert verdict["breaks"] >= 1, (
        f"Expected at least 1 behavioral break in verdict, got: {verdict}"
    )


# ---------------------------------------------------------------------------
# Test 2: anchor gate suppresses off-anchor findings
# ---------------------------------------------------------------------------
def test_integration_gate_drops_offanchor_finding(tmp_path):
    """Behavioral finding anchored to line 999 (not in changed_lines) is suppressed.

    Also exercises string-to-int coercion: the fake LLM returns line as "999"
    (a string), which the gate must coerce to int before comparing with {12, 44}.
    """
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()

    spec = intent.normalize(
        "Add tenant-scoped export; rate-limit to 10/min",
        source="prompt",
        ticket_ids=[],
    )
    intent.save_branch_record(archie_dir, BRANCH, spec)

    def fake_run_offanchor(prompt: str, root, model: str) -> str:
        # resolve
        if "acceptance criteria" in prompt and "Extract the concrete" in prompt:
            return json.dumps({
                "goals": ["tenant-scoped export"],
                "acceptance_criteria": [
                    {"id": "ac1", "text": "export is tenant-scoped"},
                    {"id": "ac2", "text": "rate limited"},
                ],
            })
        # edge-A: empty findings
        if "CRITERIA:" in prompt and "DIFF:" in prompt:
            return json.dumps({"findings": []})
        # behavioral: anchor at line "999" (string) — off-anchor
        if "behavioral" in prompt or "BLAST RADIUS" in prompt:
            return json.dumps({
                "findings": [
                    {
                        "id": "f_beh_offanchor",
                        "kind": "behavioral_break",
                        "problem_statement": "Some issue far from any changed line",
                        "file": "billing/usage.py",
                        "line": "999",   # string — exercises coercion
                        "assumptions": ["something"],
                        "evidence": ["some evidence"],
                        "falsification": "Show line 999 is changed",
                        "confidence": 0.9,
                    }
                ]
            })
        # edge-C
        if "VIOLATE any standing architectural invariant" in prompt:
            return json.dumps({"findings": []})
        return json.dumps({"findings": []})

    out = sync_review.run_sync_review(
        str(tmp_path),
        BRANCH,
        BLUEPRINT,
        IMPORT_GRAPH,
        DIFF_TEXT,
        CHANGED_FILES,
        CHANGED_LINES,   # {12, 44} — does NOT include 999
        floors={
            "behavioral_break": 0.5,
            "intent_unmet": 0.4,
            "intent_partial": 0.4,
            "intent_drift": 0.5,
        },
        run=fake_run_offanchor,
    )

    assert out["skipped"] is False

    confirmed_ids = {f["id"] for f in out["confirmed"]}
    confirmed_kinds = {f["kind"] for f in out["confirmed"]}

    # The off-anchor behavioral finding MUST be suppressed
    assert "f_beh_offanchor" not in confirmed_ids, (
        f"Off-anchor finding should have been suppressed but is in confirmed: {out['confirmed']}"
    )
    assert "behavioral_break" not in confirmed_kinds, (
        f"behavioral_break kind should be absent from confirmed (gate should suppress it): "
        f"{out['confirmed']}"
    )
