from pathlib import Path

_WF = Path(__file__).resolve().parent.parent / "archie" / "assets" / "workflow"


def test_deep_scan_product_and_rules_steps_have_tombstones():
    for step in ("step-5d-product.md", "step-6-rule-synthesis.md"):
        text = (_WF / "deep-scan" / "steps" / step).read_text()
        assert "overrides" in text.lower(), step
        assert "do not re-derive" in text.lower() or "do not carry" in text.lower(), step


def test_sync_skill_no_longer_references_ratify():
    text = (_WF / "sync" / "SKILL.md").read_text()
    assert "override-ratify" not in text
    assert "merging" in text.lower()          # merge is the ratification


def test_deep_scan_tombstones_read_overrides_json():
    for step in ("step-5d-product.md", "step-6-rule-synthesis.md"):
        text = (_WF / "deep-scan" / "steps" / step).read_text()
        assert "overrides.json" in text
        assert "overrides_history.jsonl" not in text


def test_sync_skill_has_override_fold_step():
    text = (_WF / "sync" / "SKILL.md").read_text()
    assert "Step 2b" in text
    assert "overrides.json" in text
    assert "staged" in text          # acks fold into the staged-amendment flow
