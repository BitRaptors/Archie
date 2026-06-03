"""Wiring tests: the deep-scan markdown steps must actually ACTIVATE comprehensive
depth. The unit/integration tests prove the scripts honor --comprehensive when
called with it; these tests prove the workflow text passes the flag and injects
the resolved DEPTH into subagent prompts (the gap a code review caught: leaf-level
flags existed but nothing triggered them).

Asserts on the CANONICAL tree; a separate check confirms npm-package is in sync.
"""
from pathlib import Path

WF = Path("archie/assets/workflow/deep-scan")
STEPS = WF / "steps"


def _read(p):
    return Path(p).read_text()


def test_step1_passes_comprehensive_to_scanner():
    t = _read(STEPS / "step-1-scanner.md")
    assert 'DEPTH" = "comprehensive"' in t and "COMP_FLAG" in t
    assert "scanner.py" in t and "$COMP_FLAG" in t


def test_step6_passes_comprehensive_to_renderer():
    t = _read(STEPS / "step-6-rule-synthesis.md")
    # the renderer invocation must carry the flag
    assert "renderer.py" in t and "$COMP_FLAG" in t


def test_step5_preamble_injects_depth():
    t = _read(STEPS / "step-5-wave2-reasoning.md")
    assert "Analysis depth: `<DEPTH>`" in t


def test_step6_prompt_injects_depth():
    t = _read(STEPS / "step-6-rule-synthesis.md")
    assert "Analysis depth: <DEPTH>" in t


def test_wave1_dispatch_injects_depth():
    t = _read(STEPS / "step-3-wave1" / "orchestration.md")
    assert "Analysis depth: <DEPTH>" in t


def test_npm_package_workflow_in_sync():
    """Spot-check: the npm-package mirror of the wired steps matches canonical."""
    for rel in ("steps/step-1-scanner.md", "steps/step-6-rule-synthesis.md",
                "steps/step-5-wave2-reasoning.md", "steps/step-3-wave1/orchestration.md"):
        canon = _read(WF / rel)
        mirror = _read(Path("npm-package/assets/workflow/deep-scan") / rel)
        assert canon == mirror, f"out of sync: {rel}"
