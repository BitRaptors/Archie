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


def test_coordinator_prompt_includes_completeness_validation() -> None:
    scan = _make_scan()
    groups = [_make_assignment()]
    prompt = build_coordinator_prompt(scan, groups)

    # Must include the completeness validation section
    assert "Completeness Validation" in prompt
    # Must mention specific section validation requirements
    assert "executive_summary" in prompt
    assert "confidence scores" in prompt
    assert "file_placement_rule" in prompt
    assert "naming_convention" in prompt
    assert "structure_type" in prompt


def test_coordinator_prompt_includes_full_schema_example() -> None:
    scan = _make_scan()
    groups = [_make_assignment()]
    prompt = build_coordinator_prompt(scan, groups)

    # Must include the full StructuredBlueprint schema example
    assert "Target Schema" in prompt
    assert "executive_summary" in prompt
    assert "architecture_rules" in prompt
    assert "file_placement_rules" in prompt
    assert "naming_conventions" in prompt
    assert "key_decisions" in prompt
    assert "alternatives_rejected" in prompt
    assert "implementation_guidelines" in prompt
    assert "deployment" in prompt
    assert "developer_recipes" in prompt


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


def test_subagent_prompt_includes_full_schema_example() -> None:
    """Subagent prompt must include the complete StructuredBlueprint schema."""
    scan = _make_scan()
    assignment = _make_assignment()
    prompt = build_subagent_prompt(assignment, scan)

    # Must include the full schema reference section
    assert "Complete StructuredBlueprint schema reference" in prompt

    # Must include example values from every top-level section
    assert '"executive_summary"' in prompt
    assert '"platforms"' in prompt
    assert '"confidence"' in prompt
    assert '"file_placement_rules"' in prompt
    assert '"naming_conventions"' in prompt
    assert '"architectural_style"' in prompt
    assert '"key_decisions"' in prompt
    assert '"alternatives_rejected"' in prompt
    assert '"trade_offs"' in prompt
    assert '"out_of_scope"' in prompt
    assert '"structure_type"' in prompt
    assert '"key_interfaces"' in prompt
    assert '"key_files"' in prompt
    assert '"contracts"' in prompt
    assert '"integrations"' in prompt
    assert '"pattern_selection_guide"' in prompt
    assert '"where_to_put_code"' in prompt
    assert '"error_mapping"' in prompt
    assert '"templates"' in prompt
    assert '"project_structure"' in prompt
    assert '"run_commands"' in prompt
    assert '"ui_components"' in prompt
    assert '"state_management"' in prompt
    assert '"routing"' in prompt
    assert '"data_fetching"' in prompt
    assert '"developer_recipes"' in prompt
    assert '"architecture_diagram"' in prompt
    assert '"pitfalls"' in prompt
    assert '"implementation_guidelines"' in prompt
    assert '"development_rules"' in prompt
    assert '"deployment"' in prompt


def test_subagent_prompt_includes_field_specifications() -> None:
    """Subagent prompt must include explicit field requirements."""
    scan = _make_scan()
    assignment = _make_assignment()
    prompt = build_subagent_prompt(assignment, scan)

    # Critical field requirements section must exist
    assert "Critical field requirements" in prompt

    # Component field requirements
    assert "name, location, responsibility" in prompt
    assert "platform, depends_on, exposes_to, key_interfaces, key_files" in prompt

    # Decision field requirements
    assert "title, chosen, rationale" in prompt

    # Meta field requirements
    assert "executive_summary (3-5 factual sentences)" in prompt
    assert "confidence scores per section" in prompt

    # Technology template code samples requirement
    assert "actual code samples" in prompt

    # Project structure ASCII tree requirement
    assert "ASCII directory tree" in prompt

    # Frontend completeness requirement
    assert "framework, rendering_strategy" in prompt
    assert "state_management" in prompt
    assert "global_state, server_state, local_state, rationale" in prompt
    assert "auth_required" in prompt


def test_subagent_prompt_section_guidance_has_field_details() -> None:
    """Each section guidance block must include detailed field specs."""
    scan = _make_scan()
    assignment = SubagentAssignment(
        files=["src/main.py"],
        token_total=800,
        sections=[
            "components", "architecture_rules", "decisions",
            "communication", "technology", "frontend",
            "implementation_guidelines", "deployment",
            "developer_recipes", "pitfalls", "development_rules",
        ],
        module_hint="src",
    )
    prompt = build_subagent_prompt(assignment, scan)

    # components guidance must detail all component fields
    assert "component_type" in prompt
    assert "naming_pattern" in prompt
    assert "depends_on" in prompt
    assert "exposes_to" in prompt

    # architecture_rules guidance must detail file_placement_rules fields
    assert "file_placement_rules" in prompt
    assert "naming_conventions" in prompt

    # decisions guidance must detail all decision fields
    assert "architectural_style" in prompt
    assert "alternatives_rejected" in prompt
    assert "trade_offs" in prompt

    # communication guidance must detail pattern fields
    assert "when_to_use" in prompt
    assert "how_it_works" in prompt
    assert "pattern_selection_guide" in prompt

    # technology guidance must detail stack and template fields
    assert "category" in prompt
    assert "file_path_template" in prompt
    assert "run_commands" in prompt

    # frontend guidance must detail all sub-fields
    assert "rendering_strategy" in prompt
    assert "ui_components" in prompt
    assert "state_management" in prompt
    assert "data_fetching" in prompt

    # deployment guidance must detail all fields
    assert "runtime_environment" in prompt
    assert "compute_services" in prompt
    assert "container_runtime" in prompt
    assert "ci_cd" in prompt
    assert "infrastructure_as_code" in prompt

    # implementation_guidelines guidance must detail all fields
    assert "pattern_description" in prompt
    assert "usage_example" in prompt
