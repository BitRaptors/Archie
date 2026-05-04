#!/usr/bin/env python3
"""Verify findings against actual code via parallel Haiku calls.

For each active entry in `.archie/findings.json`, spawn a Haiku subprocess
that reads the cited `triggering_call_site` (verbatim caller quote produced
by the synthesizer) plus the surrounding files, walks one level out, and
returns one of three verdicts:

    keep   — the cited call site actually triggers the failure mode; the
             finding is real and should ship.
    demote — the cited site exists but the failure mode does not fire there
             (callers enforce the missing invariant, helper is only ever
             reached via a tx-bound adapter, etc.). Pattern is a risk class,
             not a current problem; reroute to pitfalls.
    drop   — the finding's premise is unsound for this codebase. Don't track.

Output: `.archie/verdicts.json` — one verdict per active finding. The
finalize.py merge step consumes this alongside `findings.json` to apply
hysteresis-aware routing (see Phase 3).

This script follows the rest of `archie/standalone/` in shelling out to
the Claude Code CLI rather than importing the Anthropic SDK — keeps the
zero-dependency invariant and inherits the user's auth.

Usage:
    python3 verify_findings.py /path/to/project [--concurrency 10]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

CLAUDE_CLI = "claude"
DEFAULT_CONCURRENCY = 10
TIMEOUT_PER_CALL = 90  # seconds; Haiku is fast but file reads + a small walk add up
MAX_FILE_LINES_TOTAL = 800  # budget across all cited files for a single verifier call

# ---------------------------------------------------------------------------
# Verifier prompt
# ---------------------------------------------------------------------------

VERIFIER_PROMPT_TEMPLATE = """You are verifying a candidate architectural finding against actual code.

# Finding (synthesized by an upstream pass)
{finding_json}

# Cited file contents (read for you; you may also Read other files if needed)
{file_contents}

# Your job
Read the `triggering_call_site` quote in the finding. Then:

1. Confirm the quoted code exists at the cited <file>:<line>. If the quote
   is not in the file (or the file does not exist), the synthesizer
   hallucinated → DROP the finding.

2. If the quote exists, walk one level out — read the surrounding context
   and any callers of the suspect function/path. Decide:

   - KEEP: the quoted call site actually triggers the failure mode the
     finding describes. The finding is real and should ship to findings.json.

   - DEMOTE: the quoted site exists but the failure mode does NOT actually
     fire there. Common cause: the cited helper looks risky in isolation,
     but the actual callers all enforce the missing invariant — e.g. they
     only reach the helper from inside a wrapping `TransactingRepo` callback,
     they pass a tx-bound client rather than the raw one, or they bypass
     the supposedly-broken path entirely. Pattern is a real risk class but
     no current instance is actually broken. Reclassify to pitfall.

   - DROP: the finding's premise is wrong for this codebase (the cited
     mechanism does not exist, the failure mode is nonsensical for the
     paradigm, etc.). Don't track at all.

3. Be honest about uncertainty. If you can't tell whether the failure fires
   without reading more files than were inlined, you may use the Read tool
   to fetch them. If you still can't tell, default to KEEP with low
   confidence — failing open is safer than silently dropping a real
   problem.

# Output
Respond with strict JSON, NO surrounding prose, NO markdown code fences:

{{"id": "<finding id>", "verdict": "keep" | "demote" | "drop", "confidence": 0.0-1.0, "reason": "<one sentence explaining the verdict>"}}
"""


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _read_findings_store(archie_dir: Path) -> list[dict]:
    """Load active findings from `.archie/findings.json`."""
    path = archie_dir / "findings.json"
    if not path.exists():
        return []
    try:
        store = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    findings = store.get("findings") or []
    return [
        f for f in findings
        if isinstance(f, dict) and (f.get("status") or "active") == "active"
    ]


# Match `<rel/path>.<ext>(:<line>)?` patterns embedded in prose. Conservative —
# only file-extension-bearing tokens, no bare directories, to avoid sucking
# up identifiers from prose.
_FILE_REF_RE = re.compile(r"[A-Za-z0-9_./\-]+\.[a-zA-Z]{1,5}(?::\d+(?:-\d+)?)?")


def _extract_file_paths(finding: dict) -> list[str]:
    """Collect every file path referenced in triggering_call_site, evidence,
    and applies_to. Deduped, line numbers stripped."""
    seen: set[str] = set()
    out: list[str] = []

    def _add(p: str) -> None:
        p = p.split(":")[0].strip()
        if p and p not in seen:
            seen.add(p)
            out.append(p)

    tcs = finding.get("triggering_call_site") or ""
    if tcs:
        first_line = tcs.split("\n", 1)[0].strip()
        _add(first_line)
        for m in _FILE_REF_RE.findall(tcs):
            _add(m)

    for ev in finding.get("evidence") or []:
        if isinstance(ev, str):
            for m in _FILE_REF_RE.findall(ev):
                _add(m)

    for at in finding.get("applies_to") or []:
        if isinstance(at, str):
            _add(at)

    return out


def _read_files_bounded(project_root: Path, paths: list[str], budget: int = MAX_FILE_LINES_TOTAL) -> str:
    """Read up to `budget` total lines across `paths`. Returns markdown-fenced
    blocks ready for inlining into the verifier prompt."""
    chunks: list[str] = []
    remaining = budget
    for rel in paths:
        if remaining <= 0:
            chunks.append(f"## {rel}\n(skipped — file budget exhausted; verifier may Read it directly)\n")
            continue
        full = project_root / rel
        if not full.is_file():
            chunks.append(f"## {rel}\n(file not found in corpus — possible hallucinated citation)\n")
            continue
        try:
            text = full.read_text(errors="replace")
        except OSError:
            chunks.append(f"## {rel}\n(read failed)\n")
            continue
        lines = text.splitlines()
        if len(lines) > remaining:
            shown = "\n".join(lines[:remaining])
            chunks.append(
                f"## {rel}\n```\n{shown}\n```\n"
                f"... [{len(lines) - remaining} more lines truncated; verifier may Read fully]\n"
            )
            remaining = 0
        else:
            chunks.append(f"## {rel}\n```\n{text}\n```\n")
            remaining -= len(lines)
    return "\n".join(chunks) if chunks else "(no files to inline)"


# ---------------------------------------------------------------------------
# Haiku invocation
# ---------------------------------------------------------------------------

def _run_haiku(prompt: str, project_root: Path) -> str:
    """Spawn `claude -p --model haiku` synchronously. Returns result text or ""."""
    try:
        proc = subprocess.run(
            [
                CLAUDE_CLI,
                "-p",
                "--model", "haiku",
                "--output-format", "json",
                "--permission-mode", "bypassPermissions",
                "--allowedTools", "Read,Grep,Glob",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=TIMEOUT_PER_CALL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return ""
    return envelope.get("result", "") or ""


def _parse_verdict(text: str, finding_id: str) -> dict:
    """Pull the verdict JSON out of the Haiku response. Failing-open default
    on any parse error — never drop a real finding because of a parser glitch."""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    try:
        v = json.loads(s)
    except json.JSONDecodeError:
        # Try to find a JSON object anywhere in the response
        match = re.search(r"\{[^{}]*\"verdict\"[^{}]*\}", s, re.DOTALL)
        if match:
            try:
                v = json.loads(match.group(0))
            except json.JSONDecodeError:
                return _failopen_verdict(finding_id, "verifier output unparseable")
        else:
            return _failopen_verdict(finding_id, "verifier output unparseable")

    if not isinstance(v, dict):
        return _failopen_verdict(finding_id, "verifier output not an object")
    if v.get("verdict") not in {"keep", "demote", "drop"}:
        return _failopen_verdict(finding_id, f"invalid verdict={v.get('verdict')!r}")
    v.setdefault("id", finding_id)
    v.setdefault("confidence", 0.0)
    v.setdefault("reason", "")
    return v


def _failopen_verdict(finding_id: str, reason: str) -> dict:
    return {"id": finding_id, "verdict": "keep", "confidence": 0.0,
            "reason": f"{reason}; fail-open"}


# ---------------------------------------------------------------------------
# Per-finding verification
# ---------------------------------------------------------------------------

def verify_one(finding: dict, project_root: Path) -> dict:
    fid = finding.get("id") or "?"

    # Auto-demote: no triggering_call_site means it's a risk class, not a
    # current finding. The synthesizer should have classified it as a
    # pitfall already; demote it now without burning a Haiku call.
    tcs = (finding.get("triggering_call_site") or "").strip()
    if not tcs:
        return {"id": fid, "verdict": "demote", "confidence": 1.0,
                "reason": "no triggering_call_site — risk class, not current instance"}

    paths = _extract_file_paths(finding)
    if not paths:
        return {"id": fid, "verdict": "demote", "confidence": 0.8,
                "reason": "no cited files to verify against"}

    file_contents = _read_files_bounded(project_root, paths)
    finding_view = {
        k: finding.get(k)
        for k in ("id", "problem_statement", "evidence", "triggering_call_site",
                  "root_cause", "applies_to")
        if k in finding
    }
    prompt = VERIFIER_PROMPT_TEMPLATE.format(
        finding_json=json.dumps(finding_view, indent=2),
        file_contents=file_contents,
    )
    result_text = _run_haiku(prompt, project_root)
    if not result_text:
        return _failopen_verdict(fid, "verifier call failed (timeout / cli missing / non-zero exit)")
    return _parse_verdict(result_text, fid)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Verify .archie/findings.json against actual code via Haiku.")
    parser.add_argument("project_root", type=Path,
                        help="Project root (parent of .archie/).")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Max concurrent Haiku calls (default {DEFAULT_CONCURRENCY}).")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output path for verdicts.json. Default: <project>/.archie/verdicts.json")
    args = parser.parse_args()

    archie_dir = args.project_root / ".archie"
    if not archie_dir.is_dir():
        print(f"verify_findings: {archie_dir} does not exist; nothing to verify.", file=sys.stderr)
        return 1

    findings = _read_findings_store(archie_dir)
    out_path = args.output or (archie_dir / "verdicts.json")

    if not findings:
        print("verify_findings: no active findings to verify.")
        out_path.write_text(json.dumps({"verdicts": []}, indent=2))
        return 0

    print(f"verify_findings: {len(findings)} candidate(s) → "
          f"spawning Haiku batch (concurrency={args.concurrency})...")

    verdicts: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(verify_one, f, args.project_root): f for f in findings}
        for fut in concurrent.futures.as_completed(futures):
            v = fut.result()
            verdicts.append(v)
            sym = {"keep": "✓", "demote": "↓", "drop": "✗"}.get(v["verdict"], "?")
            reason = (v.get("reason") or "")[:120]
            print(f"  {sym} {v.get('id') or '?':>8}  {v.get('verdict'):>6}  conf={v.get('confidence', 0):.2f}  {reason}")

    out_path.write_text(json.dumps({"verdicts": verdicts}, indent=2))

    keep = sum(1 for v in verdicts if v["verdict"] == "keep")
    demote = sum(1 for v in verdicts if v["verdict"] == "demote")
    drop = sum(1 for v in verdicts if v["verdict"] == "drop")
    print(f"verify_findings: wrote {len(verdicts)} verdict(s) → {out_path}")
    print(f"  summary: KEEP={keep}  DEMOTE={demote}  DROP={drop}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
