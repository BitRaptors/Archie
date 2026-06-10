# tests/benchmark/test_metrics.py
import json
from archie.benchmark.metrics import parse_stream, SampleMetrics


def _assistant(blocks):
    return json.dumps({"type": "assistant", "message": {"content": blocks}})


def _tool_use(name):
    return {"type": "tool_use", "name": name, "id": "x", "input": {}}


def _result(subtype="success"):
    return json.dumps({
        "type": "result",
        "subtype": subtype,
        "total_cost_usd": 0.1234,
        "duration_ms": 5000,
        "num_turns": 7,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 200,
            "cache_read_input_tokens": 50,
            "cache_creation_input_tokens": 25,
        },
    })


def test_counts_tools_and_breakdown():
    lines = [
        json.dumps({"type": "system", "subtype": "init"}),
        _assistant([{"type": "text", "text": "hi"}, _tool_use("Read")]),
        _assistant([_tool_use("Edit"), _tool_use("Edit")]),
        _result(),
    ]
    m = parse_stream(lines)
    assert m.tool_calls == 3
    assert m.tool_breakdown == {"Read": 1, "Edit": 2}


def test_extracts_result_fields():
    m = parse_stream([_result()])
    assert m.input_tokens == 100
    assert m.output_tokens == 200
    assert m.cache_read_tokens == 50
    assert m.cache_creation_tokens == 25
    assert m.cost_usd == 0.1234
    assert m.duration_ms == 5000
    assert m.num_turns == 7
    assert m.completed is True


def test_error_result_not_completed():
    m = parse_stream([_result(subtype="error_max_turns")])
    assert m.completed is False


def test_zero_tool_run():
    m = parse_stream([_assistant([{"type": "text", "text": "done"}]), _result()])
    assert m.tool_calls == 0
    assert m.tool_breakdown == {}


def test_ignores_blank_and_malformed_lines():
    m = parse_stream(["", "  ", "not json", _result()])
    assert m.completed is True


def test_no_result_event_defaults():
    m = parse_stream([_assistant([_tool_use("Bash")])])
    assert m.tool_calls == 1
    assert m.completed is False
    assert m.cost_usd == 0.0
