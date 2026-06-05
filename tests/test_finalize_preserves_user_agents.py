"""Regression: finalize must NOT overwrite hand-curated AGENTS.md.

finalize.py used to `write_text` every rendered file blindly, which wiped a
user's hand-authored AGENTS.md (no markers) and replaced it with generated
prose. Mergeable files must go through render_mergeable so user content outside
Archie's generated block survives. See the openmeter incident: the curated
Makefile/testing tables were lost on the first finalize pass.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import finalize as F  # noqa: E402
import renderer as R  # noqa: E402


def _write_inputs(a: Path) -> list[str]:
    (a / "tmp").mkdir(parents=True, exist_ok=True)
    (a / "blueprint_raw.json").write_text(json.dumps({
        "meta": {"platforms": ["backend"]},
        "components": {"components": [{"name": "API"}]},
        "communication": {"patterns": [{"name": "REST", "how_it_works": "base"}]},
    }))
    (a / "tmp" / "design.json").write_text(json.dumps({
        "decisions": {"key_decisions": [{"title": "Use Postgres"}], "decision_chain": {"root": "r", "forces": []}},
    }))
    (a / "tmp" / "risk.json").write_text(json.dumps({"findings": [], "pitfalls": []}))
    (a / "tmp" / "overview.json").write_text(json.dumps(
        {"architecture_diagram": "graph TD\n A", "meta": {"executive_summary": "One."}}))
    return [str(a / "tmp" / f) for f in ("design.json", "risk.json", "overview.json")]


def test_finalize_preserves_hand_curated_agents_md(tmp_path):
    a = tmp_path / ".archie"
    a.mkdir()
    inputs = _write_inputs(a)

    # User's hand-curated AGENTS.md — no Archie markers.
    sentinel = "| Run all tests | `make test` |"
    (tmp_path / "AGENTS.md").write_text(
        "# OpenMeter\n\n## Testing\n\n| Task | Command |\n|--|--|\n" + sentinel + "\n")

    F.finalize(tmp_path, inputs)

    txt = (tmp_path / "AGENTS.md").read_text()
    # User content survives, generated block was appended below the markers.
    assert sentinel in txt, "hand-curated AGENTS.md content was overwritten"
    assert R.ARCHIE_MARKER_START in txt and R.ARCHIE_MARKER_END in txt
    assert txt.index(sentinel) < txt.index(R.ARCHIE_MARKER_START)

    # Re-running finalize stays idempotent and still preserves user content.
    F.finalize(tmp_path, inputs)
    txt2 = (tmp_path / "AGENTS.md").read_text()
    assert txt2.count(sentinel) == 1
    assert txt2.count(R.ARCHIE_MARKER_START) == 1
