from archie.standalone.rule_kinds import KINDS, KIND_DESCRIPTIONS, is_valid_kind, classify_kind


def test_kinds_is_a_tuple_of_strings():
    assert isinstance(KINDS, tuple)
    assert len(KINDS) > 0
    assert all(isinstance(k, str) for k in KINDS)


def test_expected_kinds_present():
    expected = {
        "decision", "pitfall", "tradeoff", "layering",
        "semantic_pattern", "file_placement", "naming_convention",
        "infrastructure", "data_contract", "coding_practice",
    }
    assert set(KINDS) == expected


def test_every_kind_has_a_description():
    for k in KINDS:
        assert k in KIND_DESCRIPTIONS
        assert len(KIND_DESCRIPTIONS[k]) > 20  # not a placeholder
    # Guard against orphan descriptions if a kind is removed from KINDS
    assert set(KIND_DESCRIPTIONS.keys()) == set(KINDS)


def test_is_valid_kind_accepts_canonical_kinds():
    for k in KINDS:
        assert is_valid_kind(k) is True


def test_is_valid_kind_rejects_unknown():
    assert is_valid_kind("unknown") is False
    assert is_valid_kind("") is False
    assert is_valid_kind(None) is False
    assert is_valid_kind("CodingPractice") is False  # case-sensitive


def test_classify_id_prefix_layer():
    assert classify_kind({"id": "layer-001"}) == "layering"


def test_classify_id_prefix_naming():
    assert classify_kind({"id": "naming-042"}) == "naming_convention"


def test_classify_id_prefix_placement():
    assert classify_kind({"id": "placement-007"}) == "file_placement"


def test_classify_id_prefix_pitfall():
    assert classify_kind({"id": "pitfall-003"}) == "pitfall"


def test_classify_id_prefix_chain_is_decision():
    assert classify_kind({"id": "chain-001"}) == "decision"


def test_classify_id_prefix_tradeoff():
    assert classify_kind({"id": "tradeoff-002"}) == "tradeoff"


def test_classify_id_prefix_pattern():
    assert classify_kind({"id": "pattern-010"}) == "semantic_pattern"


def test_classify_id_prefix_extend_is_semantic_pattern():
    assert classify_kind({"id": "extend-005"}) == "semantic_pattern"


def test_classify_severity_class_decision_violation():
    assert classify_kind({"id": "x-001", "severity_class": "decision_violation"}) == "decision"


def test_classify_severity_class_pitfall_triggered():
    assert classify_kind({"id": "x-001", "severity_class": "pitfall_triggered"}) == "pitfall"


def test_classify_severity_class_tradeoff_undermined():
    assert classify_kind({"id": "x-001", "severity_class": "tradeoff_undermined"}) == "tradeoff"


def test_classify_forbidden_imports_field_is_layering():
    assert classify_kind({"id": "x-001", "forbidden_imports": ["foo.bar"]}) == "layering"


def test_classify_allowed_dirs_is_file_placement():
    assert classify_kind({"id": "x-001", "allowed_dirs": ["src/services/"]}) == "file_placement"


def test_classify_check_file_naming_is_naming_convention():
    assert classify_kind({"id": "x-001", "check": "file_naming"}) == "naming_convention"


def test_classify_check_architectural_constraint_is_layering():
    assert classify_kind({"id": "x-001", "check": "architectural_constraint"}) == "layering"


def test_classify_check_forbidden_import_is_layering():
    assert classify_kind({"id": "x-001", "check": "forbidden_import"}) == "layering"


def test_classify_infra_path_azure_pipelines():
    rule = {"id": "x-001", "source": "azure-pipelines.yml (pool.vmImage='macos-latest')"}
    assert classify_kind(rule) == "infrastructure"


def test_classify_infra_path_dockerfile():
    assert classify_kind({"id": "x-001", "source": "Dockerfile"}) == "infrastructure"


def test_classify_infra_path_github_actions():
    assert classify_kind({"id": "x-001", "source": ".github/workflows/ci.yml"}) == "infrastructure"


def test_classify_infra_path_pyproject():
    assert classify_kind({"id": "x-001", "source": "pyproject.toml"}) == "infrastructure"


def test_classify_infra_path_package_json():
    assert classify_kind({"id": "x-001", "source": "package.json"}) == "infrastructure"


def test_classify_fallback_is_coding_practice():
    assert classify_kind({"id": "x-001", "description": "Use four-space indent"}) == "coding_practice"


def test_classify_existing_valid_kind_is_preserved():
    """If a rule already has a valid kind, classify_kind returns it unchanged."""
    assert classify_kind({"id": "x-001", "kind": "decision"}) == "decision"


def test_classify_existing_invalid_kind_is_overridden():
    """If a rule has kind 'unknown' or some bogus value, reclassify from other signals."""
    rule = {"id": "layer-001", "kind": "unknown"}
    assert classify_kind(rule) == "layering"


def test_classify_id_prefix_beats_severity_when_both_present():
    """ID prefix is the most specific signal — trust it over severity_class.

    Why: the AI agent chooses the id prefix deliberately while severity_class
    follows a coarser mapping; if they disagree, the prefix is the authoritative
    statement of conceptual type.
    """
    rule = {"id": "layer-001", "severity_class": "decision_violation"}
    assert classify_kind(rule) == "layering"


def test_classify_pattern_name_field_is_semantic_pattern():
    """pattern_name field fires when no id prefix or severity_class matches."""
    assert classify_kind({"id": "x-001", "pattern_name": "Repository"}) == "semantic_pattern"


def test_classify_empty_pattern_name_falls_through():
    """Empty string pattern_name carries no signal — fall through to coding_practice."""
    assert classify_kind({"id": "x-001", "pattern_name": ""}) == "coding_practice"


def test_classify_violation_signals_field_is_tradeoff():
    """violation_signals list fires when no id prefix or severity_class matches."""
    assert classify_kind({"id": "x-001", "violation_signals": ["sync IO in cache"]}) == "tradeoff"


def test_classify_empty_violation_signals_falls_through():
    """Empty violation_signals list carries no signal — fall through to coding_practice."""
    assert classify_kind({"id": "x-001", "violation_signals": []}) == "coding_practice"


def test_classify_infra_path_in_applies_to():
    """applies_to field is also scanned for infra path markers."""
    assert classify_kind({"id": "x-001", "applies_to": ".github/workflows/ci.yml"}) == "infrastructure"


def test_classify_infra_path_in_file_pattern():
    """file_pattern field is also scanned for infra path markers."""
    assert classify_kind({"id": "x-001", "file_pattern": "pyproject.toml"}) == "infrastructure"
