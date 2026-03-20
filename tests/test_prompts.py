"""Tests for coordinator and subagent prompt builders."""
from archie.coordinator.planner import SubagentAssignment
from archie.coordinator.prompts import build_coordinator_prompt, build_subagent_prompt
from archie.engine.models import (
    DependencyEntry,
    FileEntry,
    FrameworkSignal,
    RawScan,
)


def _make_scan() -> RawScan:
    return RawScan(
        file_tree=[
            FileEntry(path="src/main.py", size=100),
            FileEntry(path="src/utils.py", size=50),
        ],
        token_counts={"src/main.py": 800, "src/utils.py": 200},
        dependencies=[DependencyEntry(name="fastapi", version="0.110.0")],
        framework_signals=[
            FrameworkSignal(name="FastAPI", confidence=0.95),
            FrameworkSignal(name="Pydantic", confidence=0.9),
        ],
        entry_points=["src/main.py"],
    )


def _make_assignment() -> SubagentAssignment:
    return SubagentAssignment(
        files=["src/main.py", "src/utils.py"],
        token_total=1000,
        sections=["components", "technology", "architecture_rules"],
        module_hint="src",
    )


def test_coordinator_prompt_includes_scan_data() -> None:
    scan = _make_scan()
    groups = [_make_assignment()]
    prompt = build_coordinator_prompt(scan, groups)

    # Framework names must appear
    assert "FastAPI" in prompt
    assert "Pydantic" in prompt
    # File paths must appear in the tree
    assert "src/main.py" in prompt
    assert "src/utils.py" in prompt


def test_subagent_prompt_includes_files_and_sections() -> None:
    scan = _make_scan()
    assignment = _make_assignment()
    prompt = build_subagent_prompt(assignment, scan)

    # Assigned files must be listed
    assert "src/main.py" in prompt
    assert "src/utils.py" in prompt
    # Section names must appear
    assert "components" in prompt
    assert "technology" in prompt
    assert "architecture_rules" in prompt


def test_subagent_prompt_includes_module_dependencies() -> None:
    scan = RawScan(
        file_tree=[
            FileEntry(path="api/routes.py", size=200),
            FileEntry(path="api/auth.py", size=150),
            FileEntry(path="core/models.py", size=300),
            FileEntry(path="workers/tasks.py", size=250),
        ],
        token_counts={
            "api/routes.py": 500,
            "api/auth.py": 300,
            "core/models.py": 600,
            "workers/tasks.py": 400,
        },
        import_graph={
            # api/routes.py imports from core/models.py
            "api/routes.py": ["core/models.py"],
            # api/auth.py imports from core/models.py
            "api/auth.py": ["core/models.py"],
            # workers/tasks.py imports from api/routes.py
            "workers/tasks.py": ["api/routes.py"],
        },
        entry_points=["api/routes.py"],
    )
    assignment = SubagentAssignment(
        files=["api/routes.py", "api/auth.py"],
        token_total=800,
        sections=["components"],
        module_hint="api",
    )

    prompt = build_subagent_prompt(assignment, scan)

    # Should have Module Dependencies section
    assert "## Module Dependencies" in prompt
    # api imports from core
    assert "Imports from modules: core" in prompt
    # workers imports from api
    assert "Imported by modules: workers" in prompt
    # entry point
    assert "Entry points: api/routes.py" in prompt


def test_subagent_prompt_includes_schema_guidance() -> None:
    scan = _make_scan()
    assignment = _make_assignment()
    prompt = build_subagent_prompt(assignment, scan)

    # Must mention JSON output format
    assert "JSON" in prompt
