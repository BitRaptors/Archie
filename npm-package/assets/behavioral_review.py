"""Blueprint-free behavioral reviewer: reasons about the code itself
(crash / data-loss / perf / security) and consults blast radius. LLM is called
through run_verifier; prompt-builder and parser are pure and unit-tested.

Import convention: bare-name imports via sys.path so this works on Python 3.9
(archie/__init__.py uses tomllib which is 3.11+).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_cli import run_verifier        # noqa: E402
from reachability import consumers         # noqa: E402, F401 (used by callers)
from evidence_schema import make_finding   # noqa: E402

_SYSTEM = (
    "You are a behavioral code reviewer. Report only issues INTRODUCED or worsened "
    "by this diff. For each, give a falsification test ('how you'd prove me wrong'). "
    "Anchor every finding to a changed line. Return JSON {\"findings\":[...]}."
)


def build_prompt(diff_text: str, consumer_map: dict) -> str:
    radius = "\n".join(f"{f} -> {', '.join(c)}" for f, c in consumer_map.items())
    return (
        f"{_SYSTEM}\n\nDIFF:\n{diff_text}\n\n"
        f"BLAST RADIUS (changed file -> consumers):\n{radius}\n\n"
        "Each finding needs: problem_statement, file, line, assumptions[], "
        "evidence[], falsification, confidence(0-1), kind(behavioral_break)."
    )


def parse_findings(raw: str) -> list[dict]:
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start:end + 1]) if start >= 0 else {}
    except Exception:
        return []
    out = []
    for i, f in enumerate(data.get("findings", [])):
        if not f.get("falsification"):
            continue
        out.append(make_finding(
            id=f.get("id") or f"f_beh_{i}",
            kind=f.get("kind", "behavioral_break"),
            edge="B",
            problem_statement=f.get("problem_statement", ""),
            anchor={"file": f.get("file", ""), "line": f.get("line"), "changed": True},
            assumptions=f.get("assumptions", []),
            evidence=f.get("evidence", []),
            falsification=f["falsification"],
            confidence=float(f.get("confidence", 0.0)),
            source="behavioral",
            severity_class="pitfall_triggered",
        ))
    return out


def review(root, diff_text, import_graph, changed_files, run=run_verifier) -> list[dict]:
    cmap = {cf: consumers(import_graph, cf) for cf in changed_files}
    raw = run(build_prompt(diff_text, cmap), Path(root), "claude")
    return parse_findings(raw or "")
