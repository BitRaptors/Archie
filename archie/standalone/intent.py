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
        "goals": [],  # populated by the LLM resolve() step
        "acceptance_criteria": [],  # ditto
        "non_goals": [],
        "raw": raw_text,
    }


def build_resolve_prompt(raw_text):
    return ("Extract the concrete, checkable acceptance criteria and goals from this task/ticket "
            "description. Return JSON {\"goals\":[...], \"acceptance_criteria\":[{\"id\":\"ac1\",\"text\":\"...\"}]}. "
            "Each acceptance_criterion is one verifiable requirement. If the text is vague, infer the "
            "minimal criteria a reviewer would check.\n\nDESCRIPTION:\n" + (raw_text or ""))


def resolve(intent_spec, run=None):
    """Fill goals/acceptance_criteria via one LLM call; return a new spec. No-op when raw is empty."""
    if run is None:
        from agent_cli import run_verifier
        run = run_verifier
    from evidence_schema import extract_json_obj
    raw = (intent_spec.get("raw") or "").strip()
    if not raw:
        return intent_spec
    out = run(build_resolve_prompt(raw), Path("."), "claude")
    data = extract_json_obj(out or "")
    spec = dict(intent_spec)
    # Copy carried-over list fields so callers can't mutate the input via the
    # returned spec (dict() is a shallow copy — lists would otherwise alias).
    spec["ticket_ids"] = list(intent_spec.get("ticket_ids") or [])
    spec["goals"] = list(intent_spec.get("goals") or [])
    spec["non_goals"] = list(intent_spec.get("non_goals") or [])
    crit = data.get("acceptance_criteria")
    goals = data.get("goals")
    if isinstance(crit, list) and crit:
        spec["acceptance_criteria"] = [
            ({"id": c.get("id") or f"ac{i+1}", "text": c.get("text", "")} if isinstance(c, dict)
             else {"id": f"ac{i+1}", "text": str(c)}) for i, c in enumerate(crit)]
    if isinstance(goals, list) and goals:
        spec["goals"] = [str(g) for g in goals]
    return spec


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
import hashlib
import json
import os
import re
from pathlib import Path

_RANK = {"inferred": 0, "commits": 1, "pr_body": 2, "prompt": 2, "sync": 3, "linear": 3}
_TICKET_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

# C1: Denylist of common standards/protocol prefixes that look like ticket IDs
# but are never real tracker keys. A project-key allowlist (from config) would
# be the robust long-term fix; this denylist is a heuristic guard.
_TICKET_DENYLIST: frozenset[str] = frozenset({
    "CVE", "UTF", "SHA", "SHA1", "SHA256", "MD", "RFC", "ISO",
    "IPV", "IP", "CP", "UTC", "EC", "AES", "RSA", "SSE", "HTTP", "HTTPS",
})


def _is_valid_ticket(candidate: str) -> bool:
    """Return True if the ticket candidate is not a known standards prefix.

    Args:
        candidate: Full ticket string like "ARCH-123" or "CVE-2021-1234"

    Returns:
        False if the prefix before '-' is in the denylist, True otherwise
    """
    prefix = candidate.split("-")[0]
    return prefix not in _TICKET_DENYLIST


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
        if m not in seen and _is_valid_ticket(m):
            seen.add(m)
            out.append(m)
    return out


def _record_path(archie_dir: Path, branch: str) -> Path:
    """Compute the path to a branch's intent record file.

    Uses a collision-free encoding: safe ASCII slug + short stable hash of the
    original branch name so that "a/b" and "a__b" map to different files.

    Args:
        archie_dir: Path to .archie directory
        branch: Branch name

    Returns:
        Path to branch intent record
    """
    # C4: collision-free encoding — slug + 8-char SHA-1 of original name
    slug = re.sub(r"[^A-Za-z0-9._-]", "_", branch)
    suffix = hashlib.sha1(branch.encode()).hexdigest()[:8]
    safe = f"{slug}-{suffix}"
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
    discarded. For equal-rank sources, fields are merged so no previously captured
    data (ticket_ids, goals, acceptance_criteria, non_goals) is lost.

    Args:
        archie_dir: Path to .archie directory
        branch: Branch name
        spec: Intent spec dict (from normalize())
    """
    existing = load_branch_record(archie_dir, branch)
    existing_rank = _RANK.get(existing.get("source"), 0) if existing else -1
    new_rank = _RANK.get(spec.get("source"), 0)

    if existing and existing_rank > new_rank:
        # C3: keep existing higher-rank record unchanged
        return

    # C3: merge fields rather than blind replace when ranks are equal or new is higher
    if existing:
        merged = dict(spec)  # start from incoming (newer source/confidence/raw)
        # union ticket_ids — preserve all previously seen IDs
        existing_ids = existing.get("ticket_ids") or []
        new_ids = merged.get("ticket_ids") or []
        combined = list(existing_ids)
        for tid in new_ids:
            if tid not in combined:
                combined.append(tid)
        merged["ticket_ids"] = combined
        # keep existing non-empty list fields when incoming is empty
        for field in ("goals", "acceptance_criteria", "non_goals"):
            if not merged.get(field) and existing.get(field):
                merged[field] = existing[field]
        spec = merged

    p = _record_path(archie_dir, branch)
    p.parent.mkdir(parents=True, exist_ok=True)

    # J5: parent-dir symlink guard — if `.archie/intent` itself is a symlink,
    # a write through the leaf would still traverse it. Refuse (skip, no crash).
    if p.parent.is_symlink():
        return

    # C2: symlink-safe write — refuse to follow a pre-existing symlink.
    # Use O_CREAT|O_WRONLY|O_TRUNC|O_NOFOLLOW so the kernel rejects symlinks.
    if p.is_symlink():
        # Unlink the symlink and write a fresh regular file instead.
        p.unlink()

    data = json.dumps(spec, indent=2).encode()
    try:
        fd = os.open(str(p), os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    except OSError:
        # Another symlink appeared between our check and open — skip, do not follow.
        return
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


# --- Committed-intent read/write + merge ---
INTENT_FILE = "intent.json"


def merge_specs(*specs) -> dict:
    """Union acceptance_criteria (dedup by normalized text, ids reindexed), goals,
    and ticket_ids across specs. Highest-_RANK source label wins. None entries ignored.
    Never clobbers a populated field with an empty one (union only)."""
    specs = [s for s in specs if s]
    if not specs:
        return normalize("", source="inferred", ticket_ids=[])
    crit, seen = [], set()
    for s in specs:
        for c in (s.get("acceptance_criteria") or []):
            text = (c.get("text") if isinstance(c, dict) else str(c)) or ""
            key = text.strip().lower()
            if key and key not in seen:
                seen.add(key)
                crit.append({"id": f"ac{len(crit) + 1}", "text": text})
    goals, gseen = [], set()
    for s in specs:
        for g in (s.get("goals") or []):
            k = str(g).strip().lower()
            if k and k not in gseen:
                gseen.add(k)
                goals.append(str(g))
    non_goals, ngseen = [], set()
    for s in specs:
        for g in (s.get("non_goals") or []):
            k = str(g).strip().lower()
            if k and k not in ngseen:
                ngseen.add(k)
                non_goals.append(str(g))
    tickets = []
    for s in specs:
        ids = list(s.get("ticket_ids") or [])
        single = s.get("ticket_id")
        if single and single not in ids:
            ids.append(single)
        for t in ids:
            if t and t not in tickets:
                tickets.append(t)
    best = max(specs, key=lambda s: _RANK.get(s.get("source"), 0))
    raw = "\n\n".join(s.get("raw") for s in specs if s.get("raw"))
    return {
        "source": best.get("source", "inferred"),
        "confidence": best.get("confidence", "low"),
        "ticket_ids": tickets,
        "goals": goals,
        "acceptance_criteria": crit,
        "non_goals": non_goals,
        "raw": raw,
    }


def load_committed_intent(root) -> dict | None:
    """Read .archie/intent.json -> spec dict, or None if absent/malformed/non-dict."""
    p = Path(root) / ".archie" / INTENT_FILE
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def write_committed_intent(root, spec: dict) -> None:
    """Merge `spec` over any existing .archie/intent.json and write atomically."""
    archie = Path(root) / ".archie"
    archie.mkdir(parents=True, exist_ok=True)
    existing = load_committed_intent(root)
    merged = merge_specs(existing, spec) if existing else spec
    p = archie / INTENT_FILE
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2))
    os.replace(tmp, p)


def intent_brief(spec) -> str:
    """One short block summarizing the intended change, for code-review prompts. '' if empty."""
    if not spec:
        return ""
    lines = []
    goals = spec.get("goals") or []
    if goals:
        lines.append("Goals: " + "; ".join(str(g) for g in goals))
    for c in (spec.get("acceptance_criteria") or []):
        text = c.get("text") if isinstance(c, dict) else str(c)
        if text:
            lines.append(f"- {text}")
    non_goals = spec.get("non_goals") or []
    if non_goals:
        lines.append("Non-goals: " + "; ".join(str(g) for g in non_goals))
    return "\n".join(lines).strip()
