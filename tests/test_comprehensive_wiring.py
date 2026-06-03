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


DEPTH_REDERIVE = ".run_context.depth"


def test_step1_passes_comprehensive_to_scanner():
    t = _read(STEPS / "step-1-scanner.md")
    assert 'DEPTH" = "comprehensive"' in t and "COMP_FLAG" in t
    assert "scanner.py" in t and "$COMP_FLAG" in t
    # must re-derive DEPTH from disk, not rely on cross-step shell persistence
    assert DEPTH_REDERIVE in t


def test_step6_passes_comprehensive_to_renderer():
    t = _read(STEPS / "step-6-rule-synthesis.md")
    # the renderer invocation must carry the flag
    assert "renderer.py" in t and "$COMP_FLAG" in t
    assert DEPTH_REDERIVE in t


def test_step9_rederives_depth_from_disk():
    t = _read(STEPS / "step-9-drift.md")
    assert DEPTH_REDERIVE in t and "SINCE_ARGS" in t


CONTRACT = "COMPREHENSIVE MODE — be exhaustive"


def test_skill_has_global_contract():
    t = _read(WF / "SKILL.md")
    assert "Comprehensive Mode Contract" in t
    # the contract must state the FLOOR-not-ceiling rule and the two surviving limits
    assert "FLOOR" in t and "8-12 nodes" in t


def test_step5_preamble_injects_contract():
    # Wave-2 preamble covers design + risk + overview, so this is what makes the
    # Risk agent's findings/pitfalls unbounded (the previously-missed step-5b).
    t = _read(STEPS / "step-5-wave2-reasoning.md")
    assert CONTRACT in t


def test_step6_prompt_injects_contract():
    t = _read(STEPS / "step-6-rule-synthesis.md")
    assert CONTRACT in t


def test_wave1_dispatch_injects_contract():
    t = _read(STEPS / "step-3-wave1" / "orchestration.md")
    assert CONTRACT in t


def test_npm_package_workflow_in_sync():
    """Spot-check: the npm-package mirror of the wired steps matches canonical."""
    for rel in ("steps/step-1-scanner.md", "steps/step-6-rule-synthesis.md",
                "steps/step-5-wave2-reasoning.md", "steps/step-3-wave1/orchestration.md"):
        canon = _read(WF / rel)
        mirror = _read(Path("npm-package/assets/workflow/deep-scan") / rel)
        assert canon == mirror, f"out of sync: {rel}"
