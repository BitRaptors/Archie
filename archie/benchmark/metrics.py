# archie/benchmark/metrics.py
import json
from dataclasses import dataclass, field


@dataclass
class SampleMetrics:
    tool_calls: int = 0
    tool_breakdown: dict = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    completed: bool = False


def parse_stream(lines):
    m = SampleMetrics()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = ev.get("type")
        if etype == "assistant":
            for block in ev.get("message", {}).get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    m.tool_calls += 1
                    name = block.get("name", "unknown")
                    m.tool_breakdown[name] = m.tool_breakdown.get(name, 0) + 1
        elif etype == "result":
            usage = ev.get("usage", {}) or {}
            m.input_tokens = usage.get("input_tokens", 0)
            m.output_tokens = usage.get("output_tokens", 0)
            m.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
            m.cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)
            m.cost_usd = ev.get("total_cost_usd", 0.0)
            m.duration_ms = ev.get("duration_ms", 0)
            m.num_turns = ev.get("num_turns", 0)
            m.completed = ev.get("subtype") == "success"
    return m
