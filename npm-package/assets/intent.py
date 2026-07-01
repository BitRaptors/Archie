"""Intent resolver: normalize any intent source to one shape and expose the
confidence ceiling that caps edge-A findings (the anti-noise valve for the
no-ticket case).
"""
from __future__ import annotations

_CONF_BY_SOURCE = {
    "linear": "high",
    "prompt": "medium",
    "pr_body": "medium",
    "commits": "low",
    "inferred": "low",
}
CONFIDENCE_CEILING = {"high": 1.0, "medium": 0.75, "low": 0.5}


def normalize(raw_text: str, source: str, ticket_ids: list[str]) -> dict:
    """Normalize any intent source to a single spec shape.

    Args:
        raw_text: Raw input text (ticket body, prompt, commits, etc.)
        source: Intent source ("linear", "prompt", "pr_body", "commits", "inferred")
        ticket_ids: List of linked ticket IDs

    Returns:
        dict with keys: source, confidence, ticket_ids, goals,
        acceptance_criteria, non_goals, raw
    """
    conf = _CONF_BY_SOURCE.get(source, "low")
    return {
        "source": source,
        "confidence": conf,
        "ticket_ids": list(ticket_ids),
        "goals": [],  # populated by the LLM normalize step in resolve()
        "acceptance_criteria": [],  # ditto
        "non_goals": [],
        "raw": raw_text,
    }


def ceiling_for(intent_spec: dict) -> float:
    """Return the confidence ceiling (noise-suppression valve) for a given spec.

    The ceiling caps edge-A findings to manage false-positive risk in
    low-confidence scenarios (e.g., inferred intent, no ticket).

    Args:
        intent_spec: dict with "confidence" key

    Returns:
        float in [0.5, 1.0]
    """
    return CONFIDENCE_CEILING.get(intent_spec.get("confidence", "low"), 0.5)
