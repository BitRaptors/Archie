"""Tests for comprehensive-depth render-slice lifting in arch_review.py."""
import sys
from importlib import import_module

sys.path.insert(0, "archie/standalone")
arch_review = import_module("arch_review")


def _blueprint_with_many(tmp_path):
    """Write a blueprint.json with >10 dev_rules, >8 key_decisions,
    >5 trade_offs (each with >5 signals), and >10 components."""
    import json

    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    bp = {
        "decisions": {
            "key_decisions": [
                {"title": f"Decision {i}", "chosen": f"choice {i}"}
                for i in range(12)
            ],
            "trade_offs": [
                {
                    "accept": f"tradeoff {i}",
                    "violation_signals": [f"sig{i}-{j}" for j in range(8)],
                }
                for i in range(9)
            ],
        },
        "development_rules": [
            {"rule": f"rule {i}"} for i in range(15)
        ],
        "components": {
            "components": [
                {"name": f"Comp{i}", "location": f"src/c{i}", "depends_on": []}
                for i in range(14)
            ]
        },
    }
    (archie_dir / "blueprint.json").write_text(json.dumps(bp))
    return tmp_path


def _reset_flag():
    arch_review._COMPREHENSIVE = False


def test_default_caps_render_slices(tmp_path):
    _reset_flag()
    root = _blueprint_with_many(tmp_path)
    out = arch_review._get_blueprint_context(root)

    # key_decisions capped at 8
    assert out.count("**Decision ") == 8
    assert "**Decision 7**" in out
    assert "**Decision 8**" not in out

    # trade_offs capped at 5
    assert out.count("tradeoff ") == 5
    assert "tradeoff 4" in out
    assert "tradeoff 5" not in out

    # signals per trade-off capped at 5
    assert "sig0-4" in out
    assert "sig0-5" not in out

    # development_rules capped at 10
    assert out.count("- rule ") == 10
    assert "- rule 9" in out
    assert "- rule 10" not in out

    # components capped at 10
    assert out.count("**Comp") == 10
    assert "**Comp9**" in out
    assert "**Comp10**" not in out


def test_comprehensive_renders_all_slices(tmp_path):
    _reset_flag()
    arch_review._COMPREHENSIVE = True
    try:
        root = _blueprint_with_many(tmp_path)
        out = arch_review._get_blueprint_context(root)

        # all 12 key_decisions
        assert out.count("**Decision ") == 12
        assert "**Decision 11**" in out

        # all 9 trade_offs
        assert out.count("tradeoff ") == 9
        assert "tradeoff 8" in out

        # all 8 signals for trade-off 0
        assert "sig0-7" in out

        # all 15 development_rules
        assert out.count("- rule ") == 15
        assert "- rule 14" in out

        # all 14 components
        assert out.count("**Comp") == 14
        assert "**Comp13**" in out
    finally:
        _reset_flag()
