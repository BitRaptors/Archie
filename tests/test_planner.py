"""Tests for archie.coordinator.planner."""
from archie.coordinator.planner import (
    ALL_SECTIONS,
    SubagentAssignment,
    plan_subagent_groups,
)
from archie.engine.models import FileEntry, RawScan


def _scan(paths_tokens: list[tuple[str, int]]) -> RawScan:
    """Helper to build a RawScan with given file paths and token counts."""
    return RawScan(
        file_tree=[FileEntry(path=p) for p, _ in paths_tokens],
        token_counts={p: t for p, t in paths_tokens},
    )


def test_small_repo_single_group():
    scan = _scan([
        ("src/main.py", 2000),
        ("src/utils.py", 1000),
        ("tests/test_main.py", 3000),
    ])
    groups = plan_subagent_groups(scan, token_budget=150_000)
    assert len(groups) == 1
    assert groups[0].token_total == 6000
    assert set(groups[0].files) == {"src/main.py", "src/utils.py", "tests/test_main.py"}


def test_large_repo_splits_by_budget():
    scan = _scan([
        ("alpha/big.py", 80_000),
        ("beta/big.py", 60_000),
        ("gamma/big.py", 40_000),
    ])
    groups = plan_subagent_groups(scan, token_budget=150_000)
    assert len(groups) == 2
    total = sum(g.token_total for g in groups)
    assert total == 180_000


def test_groups_respect_module_boundaries():
    scan = _scan([
        ("src/api/routes.py", 10_000),
        ("src/api/views.py", 10_000),
        ("lib/helpers.py", 10_000),
    ])
    groups = plan_subagent_groups(scan, token_budget=25_000)
    # src and lib should be in separate groups because src alone is 20k
    # and adding lib (10k) would exceed 25k.
    assert len(groups) == 2
    # Files from src/api must stay in the same group.
    src_group = [g for g in groups if "src/api/routes.py" in g.files][0]
    assert "src/api/views.py" in src_group.files


def test_assignment_has_sections():
    scan = _scan([
        ("src/main.py", 1000),
    ])
    groups = plan_subagent_groups(scan, token_budget=150_000)
    for group in groups:
        assert group.sections == ALL_SECTIONS


def test_empty_scan():
    scan = RawScan()
    groups = plan_subagent_groups(scan)
    assert groups == []
