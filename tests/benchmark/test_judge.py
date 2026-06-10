# tests/benchmark/test_judge.py
import json
import pytest
from archie.benchmark import judge


def test_assign_order_is_seed_deterministic():
    assert judge.assign_order(0) == ("a", "b")
    assert judge.assign_order(2) == ("a", "b")
    assert judge.assign_order(1) == ("b", "a")
    assert judge.assign_order(3) == ("b", "a")


def test_parse_judge_output_extracts_embedded_json():
    text = 'Here is my verdict:\n{"variant_a": {"overall": 8}, "variant_b": {"overall": 5}}\nThanks'
    parsed = judge.parse_judge_output(text)
    assert parsed["variant_a"]["overall"] == 8


def test_parse_judge_output_raises_without_json():
    with pytest.raises(ValueError, match="JSON"):
        judge.parse_judge_output("no json here")


def test_run_judge_maps_variants_to_arms_seed_even():
    # seed even -> treatment is variant_a
    payload = json.dumps({"variant_a": {"overall": 9}, "variant_b": {"overall": 4}})
    calls = []

    def fake_runner(prompt, model, timeout):
        calls.append((prompt, model))
        return payload

    result = judge.run_judge("task", "TREAT_DIFF", "CTRL_DIFF",
                             rubric=["correctness"], model="m", seed=0,
                             _runner=fake_runner)
    assert result["treatment"]["overall"] == 9
    assert result["control"]["overall"] == 4
    assert result["seed"] == 0
    # variant A diff (shown first) must be the treatment diff for an even seed
    assert calls[0][0].index("TREAT_DIFF") < calls[0][0].index("CTRL_DIFF")


def test_run_judge_maps_variants_to_arms_seed_odd():
    # seed odd -> treatment is variant_b
    payload = json.dumps({"variant_a": {"overall": 3}, "variant_b": {"overall": 7}})
    result = judge.run_judge("task", "TREAT_DIFF", "CTRL_DIFF",
                             rubric=["correctness"], model="m", seed=1,
                             _runner=lambda p, m, t: payload)
    assert result["treatment"]["overall"] == 7
    assert result["control"]["overall"] == 3


def test_run_judge_retries_once_on_bad_json():
    outputs = ["garbage", json.dumps({"variant_a": {"overall": 6}, "variant_b": {"overall": 6}})]

    def flaky(prompt, model, timeout):
        return outputs.pop(0)

    result = judge.run_judge("task", "A", "B", rubric=["c"], model="m", seed=0, _runner=flaky)
    assert result["treatment"]["overall"] == 6
    assert outputs == []  # both outputs consumed -> retried exactly once


def test_run_judge_raises_after_two_failures():
    with pytest.raises(ValueError):
        judge.run_judge("task", "A", "B", rubric=["c"], model="m", seed=0,
                        _runner=lambda p, m, t: "still garbage")
