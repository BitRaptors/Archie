# tests/benchmark/test_schema.py
from pathlib import Path

SQL = Path(__file__).parent.parent.parent / "archie" / "benchmark" / "schema.sql"


def test_schema_defines_both_tables_and_view():
    text = SQL.read_text()
    assert "create table" in text.lower()
    assert "benchmark_runs" in text
    assert "benchmark_samples" in text
    assert "benchmark_summary" in text
    # key sample columns referenced by store.py / aggregate.py exist
    for col in ["tool_calls", "tool_breakdown", "cost_usd", "quality_score",
                "cache_read_tokens", "judge_seed", "completed", "arm"]:
        assert col in text
    # prep cost lives on the run, separate from measured samples
    assert "prep_cost_usd" in text
