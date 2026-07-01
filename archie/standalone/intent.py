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


# --- Intent ladder resolution + per-branch record ---
import re
import json
from pathlib import Path

_RANK = {"inferred": 0, "commits": 1, "pr_body": 2, "prompt": 2, "linear": 3}
_TICKET_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def ticket_ids_from(branch: str, pr_body: str, commit_msgs: list[str]) -> list[str]:
    """Extract ticket IDs from branch name, PR body, and commit messages.

    Args:
        branch: Branch name (e.g., "feature/ARCH-123-export")
        pr_body: PR body text
        commit_msgs: List of commit messages

    Returns:
        List of unique ticket IDs in order of first appearance
    """
    text = " ".join([branch or "", pr_body or "", " ".join(commit_msgs or [])])
    seen, out = set(), []
    for m in _TICKET_RE.findall(text):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _record_path(archie_dir: Path, branch: str) -> Path:
    """Compute the path to a branch's intent record file.

    Args:
        archie_dir: Path to .archie directory
        branch: Branch name

    Returns:
        Path to branch intent record (branch name with / → __)
    """
    safe = branch.replace("/", "__")
    return archie_dir / "intent" / f"{safe}.json"


def load_branch_record(archie_dir: Path, branch: str) -> dict | None:
    """Load a branch's intent record from disk.

    Args:
        archie_dir: Path to .archie directory
        branch: Branch name

    Returns:
        Intent spec dict, or None if record doesn't exist or is malformed
    """
    p = _record_path(archie_dir, branch)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def save_branch_record(archie_dir: Path, branch: str, spec: dict) -> None:
    """Save a branch's intent record to disk, merging over lower-confidence existing record.

    Never downgrades confidence: if a higher-ranked source exists, the new spec is
    discarded.

    Args:
        archie_dir: Path to .archie directory
        branch: Branch name
        spec: Intent spec dict (from normalize())
    """
    existing = load_branch_record(archie_dir, branch)
    if existing and _RANK.get(existing.get("source"), 0) > _RANK.get(spec.get("source"), 0):
        return
    p = _record_path(archie_dir, branch)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(spec, indent=2))
