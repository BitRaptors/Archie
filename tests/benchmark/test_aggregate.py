from archie.benchmark.aggregate import aggregate_samples


def _s(arm, cost, tools, quality, completed=True):
    return {"arm": arm, "cost_usd": cost, "tool_calls": tools,
            "duration_ms": 1000, "input_tokens": 10, "output_tokens": 20,
            "quality_score": quality, "completed": completed}


def test_per_arm_means():
    samples = [
        _s("treatment", 1.0, 10, 8.0),
        _s("treatment", 3.0, 20, 9.0),
        _s("control", 2.0, 30, 6.0),
        _s("control", 4.0, 40, 7.0),
    ]
    agg = aggregate_samples(samples)
    assert agg["treatment"]["cost_usd_mean"] == 2.0
    assert agg["treatment"]["tool_calls_mean"] == 15.0
    assert agg["treatment"]["quality_mean"] == 8.5
    assert agg["control"]["cost_usd_mean"] == 3.0
    assert agg["treatment"]["n"] == 2
    assert agg["treatment"]["completed_n"] == 2


def test_savings_percentages():
    samples = [_s("treatment", 1.0, 10, 8.0), _s("control", 2.0, 20, 8.0)]
    agg = aggregate_samples(samples)
    # treatment cost is 50% lower than control
    assert agg["savings"]["cost_pct"] == 50.0
    assert agg["savings"]["tool_calls_pct"] == 50.0


def test_quality_ignores_none_scores():
    samples = [
        _s("treatment", 1.0, 10, None, completed=False),
        _s("treatment", 1.0, 10, 8.0),
        _s("control", 1.0, 10, 6.0),
    ]
    agg = aggregate_samples(samples)
    assert agg["treatment"]["quality_mean"] == 8.0  # None excluded
    assert agg["treatment"]["completed_n"] == 1


def test_handles_empty_arm():
    samples = [_s("treatment", 1.0, 10, 8.0)]
    agg = aggregate_samples(samples)
    assert agg["control"]["n"] == 0
    assert agg["control"]["cost_usd_mean"] is None
    assert agg["savings"]["cost_pct"] is None


def test_attempted_n_and_quality_excludes_not_attempted():
    samples = [
        {"arm": "treatment", "cost_usd": 1.0, "tool_calls": 9, "duration_ms": 100,
         "input_tokens": 1, "output_tokens": 1, "quality_score": 8.0,
         "completed": True, "attempted": True},
        {"arm": "control", "cost_usd": 0.5, "tool_calls": 28, "duration_ms": 100,
         "input_tokens": 1, "output_tokens": 1, "quality_score": 1.0,
         "completed": True, "attempted": False},
    ]
    agg = aggregate_samples(samples)
    assert agg["treatment"]["attempted_n"] == 1
    assert agg["control"]["attempted_n"] == 0
    # control's q1 came from an empty diff -> excluded from quality_mean
    assert agg["treatment"]["quality_mean"] == 8.0
    assert agg["control"]["quality_mean"] is None


def test_attempted_defaults_true_for_legacy_samples():
    # samples without an explicit 'attempted' key count as attempted (back-compat)
    agg = aggregate_samples([_s("treatment", 1.0, 10, 8.0)])
    assert agg["treatment"]["attempted_n"] == 1
    assert agg["treatment"]["quality_mean"] == 8.0
