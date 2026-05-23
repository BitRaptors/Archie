from archie.standalone.rule_kinds import KINDS, KIND_DESCRIPTIONS, is_valid_kind


def test_kinds_is_a_tuple_of_strings():
    assert isinstance(KINDS, tuple)
    assert len(KINDS) > 0
    assert all(isinstance(k, str) for k in KINDS)


def test_expected_kinds_present():
    expected = {
        "decision", "pitfall", "tradeoff", "layering",
        "semantic_pattern", "file_placement", "naming_convention",
        "infrastructure", "coding_practice",
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
