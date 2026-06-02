NUMERIC_FIELDS = ["cost_usd", "tool_calls", "duration_ms", "input_tokens", "output_tokens"]


def _mean(values):
    return sum(values) / len(values) if values else None


def _arm_stats(samples):
    # A sample "attempted" the task if it produced a non-empty diff. Legacy
    # samples without the flag are treated as attempted (back-compat).
    stats = {
        "n": len(samples),
        "completed_n": sum(1 for s in samples if s.get("completed")),
        "attempted_n": sum(1 for s in samples if s.get("attempted", True)),
    }
    for f in NUMERIC_FIELDS:
        vals = [s[f] for s in samples if s.get(f) is not None]
        stats[f + "_mean"] = _mean(vals)
    # Quality only counts attempts: an empty-diff run that the judge scored low
    # is "not attempted", not "poor quality" — exclude it from the mean.
    qvals = [s["quality_score"] for s in samples
             if s.get("attempted", True) and s.get("quality_score") is not None]
    stats["quality_mean"] = _mean(qvals)
    return stats


def _pct_lower(treatment, control):
    """Percent reduction of treatment relative to control (positive = treatment cheaper)."""
    if treatment is None or control is None or control == 0:
        return None
    return round((control - treatment) / control * 100, 1)


def aggregate_samples(samples):
    treatment = [s for s in samples if s.get("arm") == "treatment"]
    control = [s for s in samples if s.get("arm") == "control"]
    t_stats = _arm_stats(treatment)
    c_stats = _arm_stats(control)
    return {
        "treatment": t_stats,
        "control": c_stats,
        "savings": {
            "cost_pct": _pct_lower(t_stats["cost_usd_mean"], c_stats["cost_usd_mean"]),
            "tool_calls_pct": _pct_lower(t_stats["tool_calls_mean"], c_stats["tool_calls_mean"]),
            "duration_pct": _pct_lower(t_stats["duration_ms_mean"], c_stats["duration_ms_mean"]),
        },
    }
