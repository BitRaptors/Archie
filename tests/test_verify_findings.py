"""Regression tests for the Haiku finding verifier (`verify_findings.py`).

We don't actually invoke the claude CLI here — the network call is replaced
by a stub. What we test:

- File-path extraction from triggering_call_site / evidence / applies_to
  (so the verifier inlines the right files for Haiku to read).
- Verdict parsing handles strict JSON, fenced JSON, embedded JSON, and
  malformed responses (the parser must fail open, not silently drop).
- Auto-demote when the synthesizer left triggering_call_site empty —
  this short-circuits without burning a Haiku call.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

import verify_findings  # noqa: E402


# ---------------------------------------------------------------------------
# _extract_file_paths
# ---------------------------------------------------------------------------

def test_extract_file_paths_from_triggering_call_site_first_line() -> None:
    finding = {
        "triggering_call_site": "src/auth/login.py:42\n    return foo(client)",
    }
    paths = verify_findings._extract_file_paths(finding)
    assert "src/auth/login.py" in paths


def test_extract_file_paths_dedupes() -> None:
    finding = {
        "triggering_call_site": "src/foo.go:10\nresult := bar(client)",
        "evidence": ["src/foo.go:10 — uses raw client"],
        "applies_to": ["src/foo.go"],
    }
    paths = verify_findings._extract_file_paths(finding)
    assert paths.count("src/foo.go") == 1


def test_extract_file_paths_pulls_secondary_refs_from_body() -> None:
    finding = {
        "triggering_call_site": (
            "openmeter/billing/charges/lock.go:15\n"
            "    return lockr.NewKey(\"namespace\", chargeID.Namespace)"
        ),
        "evidence": [
            "see also openmeter/subscription/locks.go:6 for a different shape",
        ],
    }
    paths = verify_findings._extract_file_paths(finding)
    assert "openmeter/billing/charges/lock.go" in paths
    assert "openmeter/subscription/locks.go" in paths


def test_extract_file_paths_empty_finding_returns_empty() -> None:
    assert verify_findings._extract_file_paths({}) == []


# ---------------------------------------------------------------------------
# _parse_verdict
# ---------------------------------------------------------------------------

def test_parse_verdict_strict_json() -> None:
    text = '{"id": "f_0001", "verdict": "demote", "confidence": 0.9, "reason": "callers wrap tx"}'
    v = verify_findings._parse_verdict(text, "f_0001")
    assert v["verdict"] == "demote"
    assert v["confidence"] == 0.9
    assert "callers wrap tx" in v["reason"]


def test_parse_verdict_fenced_json() -> None:
    text = '```json\n{"id": "f_0001", "verdict": "keep", "confidence": 0.8, "reason": "real"}\n```'
    v = verify_findings._parse_verdict(text, "f_0001")
    assert v["verdict"] == "keep"


def test_parse_verdict_embedded_json_with_surrounding_prose() -> None:
    text = (
        "After analysis I conclude:\n"
        '{"id": "f_0001", "verdict": "drop", "confidence": 0.95, "reason": "premise unsound"}\n'
        "Hope this helps."
    )
    v = verify_findings._parse_verdict(text, "f_0001")
    assert v["verdict"] == "drop"


def test_parse_verdict_malformed_fails_open() -> None:
    text = "this is not json at all"
    v = verify_findings._parse_verdict(text, "f_0001")
    assert v["verdict"] == "keep"  # fail open
    assert v["confidence"] == 0.0
    assert "fail-open" in v["reason"]


def test_parse_verdict_invalid_verdict_value_fails_open() -> None:
    text = '{"id": "f_0001", "verdict": "yolo", "confidence": 0.9}'
    v = verify_findings._parse_verdict(text, "f_0001")
    assert v["verdict"] == "keep"
    assert v["confidence"] == 0.0
    assert "fail-open" in v["reason"]


# ---------------------------------------------------------------------------
# verify_one — short-circuits without a Haiku call
# ---------------------------------------------------------------------------

def test_verify_one_demotes_when_no_triggering_call_site(tmp_path: Path) -> None:
    """Synthesizer should always emit triggering_call_site for findings;
    if missing, treat as a mis-filed risk class and demote without burning
    a Haiku call."""
    finding = {
        "id": "f_0001",
        "problem_statement": "Some risk class",
        "evidence": ["AGENTS.md mandates X"],
        "applies_to": ["src/"],
        # NOTE: triggering_call_site intentionally absent
    }
    v = verify_findings.verify_one(finding, tmp_path)
    assert v["id"] == "f_0001"
    assert v["verdict"] == "demote"
    assert v["confidence"] == 1.0
    assert "no triggering_call_site" in v["reason"]


def test_verify_one_demotes_when_no_cited_files(tmp_path: Path) -> None:
    """If triggering_call_site exists but doesn't cite any file we can read,
    we can't verify against code → demote with lower confidence."""
    finding = {
        "id": "f_0002",
        "problem_statement": "Vague observation",
        "triggering_call_site": "the function does X",  # no file:line ref
        "evidence": ["narrative"],
    }
    v = verify_findings.verify_one(finding, tmp_path)
    assert v["verdict"] == "demote"
    assert v["confidence"] < 1.0


def test_verify_one_failopen_when_haiku_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Real triggering_call_site, real cited file, but the claude CLI is
    unreachable — verifier must NOT silently drop. Default to keep with
    confidence 0.0 so finalize/apply_verdicts treats it as no-change."""
    cited = tmp_path / "src" / "foo.py"
    cited.parent.mkdir(parents=True)
    cited.write_text("def trigger():\n    return bad()\n")

    finding = {
        "id": "f_0003",
        "problem_statement": "Real-looking finding",
        "triggering_call_site": "src/foo.py:2\n    return bad()",
        "applies_to": ["src/foo.py"],
    }

    # Stub Haiku to return empty (CLI failure path).
    monkeypatch.setattr(verify_findings, "_run_haiku", lambda prompt, root: "")

    v = verify_findings.verify_one(finding, tmp_path)
    assert v["verdict"] == "keep"
    assert v["confidence"] == 0.0
    assert "fail-open" in v["reason"]


def test_verify_one_passes_haiku_response_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cited = tmp_path / "src" / "foo.py"
    cited.parent.mkdir(parents=True)
    cited.write_text("def trigger():\n    return bad()\n")

    finding = {
        "id": "f_0004",
        "problem_statement": "Real",
        "triggering_call_site": "src/foo.py:2\n    return bad()",
        "applies_to": ["src/foo.py"],
    }

    haiku_response = (
        '{"id": "f_0004", "verdict": "demote", "confidence": 0.85, '
        '"reason": "callers wrap with safe_bad()"}'
    )
    monkeypatch.setattr(verify_findings, "_run_haiku", lambda prompt, root: haiku_response)

    v = verify_findings.verify_one(finding, tmp_path)
    assert v["verdict"] == "demote"
    assert v["confidence"] == 0.85
    assert "safe_bad" in v["reason"]
