#!/usr/bin/env python3
"""Archie integrity — compute and render the Architecture Integrity Score (AIS).

Reads a repo's `.archie/` artifacts, derives the four headline axes, computes the
AIS, and prints a WORKLIST-FIRST report: the open divergences (named, located,
fixable) are the body; the number is only the roll-up.

    python3 score.py /path/to/repo            # human report
    python3 score.py /path/to/repo --json     # machine-readable

Fail-soft everywhere: missing/unreadable artifacts degrade to "unmeasured" or a
"no baseline" notice, never a crash. Zero dependencies beyond the Python 3.9+
stdlib; no network, no LLM. The block decision is NOT here — this only measures.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scoring  # noqa: E402

_HERE = Path(__file__).resolve().parent
_SRC_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java",
    ".kt", ".rb", ".php", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".swift", ".scala",
}
_SKIP_DIRS = {".git", "node_modules", "dist", "build", ".archie", "vendor",
              "__pycache__", ".venv", "venv", ".next", "target"}

SCORE_VERSION = "v0"


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run_check_rules(repo: Path) -> dict:
    """Run check_rules.py as a subprocess; parse the JSON it prints to stdout."""
    try:
        proc = subprocess.run(
            [sys.executable, str(_HERE / "check_rules.py"), str(repo)],
            capture_output=True, text=True, timeout=180,
        )
        out = proc.stdout
        start = out.index("{")
        return json.loads(out[start:])
    except Exception:
        return {"violations": [], "rules_checked": 0, "violations_count": 0}


def _accepted_rule_ids(archie: Path) -> set:
    """rule_ids acknowledged by staged amendments in .archie/changes/ (the Accept path)."""
    ids: set = set()
    changes = archie / "changes"
    if not changes.is_dir():
        return ids
    for f in sorted(changes.glob("*.json")):
        data = _read_json(f) or {}
        claims = data.get("claims") or data.get("staged_amendments") or []
        for c in claims:
            rid = c.get("rule_id") if isinstance(c, dict) else None
            if rid:
                ids.add(rid)
    return ids


def _count_loc(repo: Path) -> int:
    total = 0
    for dp, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for f in files:
            if os.path.splitext(f)[1].lower() in _SRC_EXT:
                try:
                    with open(os.path.join(dp, f), encoding="utf-8", errors="ignore") as fh:
                        total += sum(1 for _ in fh)
                except Exception:
                    pass
    return total


def _rules_index(archie: Path) -> dict:
    """id -> rule, from rules.json (+ platform_rules.json), for worklist labels."""
    index: dict = {}
    for name in ("platform_rules.json", "rules.json"):
        data = _read_json(archie / name)
        rules = data.get("rules") if isinstance(data, dict) else data
        for r in rules or []:
            if isinstance(r, dict) and r.get("id"):
                index[r["id"]] = r
    return index


def _unguarded_laws(blueprint: dict) -> list:
    out = []
    for key in ("domain_invariants", "derived_invariants"):
        for law in (blueprint.get(key) or []):
            if isinstance(law, dict) and not scoring._is_enforced(law):
                out.append(law.get("id") or law.get("name") or "?")
    for law in (blueprint.get("unenforced_invariants") or []):
        if isinstance(law, dict):
            out.append(law.get("id") or law.get("name") or "?")
    return out


# ── diff-scoping (the PR gate) ───────────────────────────────────────────────
# Grounded = the blocking class (decision_violation / pitfall / mechanical /
# domain_invariant — all of which check_rules maps to severity "error").
GROUNDED_SEVERITIES = {"error"}


def is_grounded(severity) -> bool:
    return severity in GROUNDED_SEVERITIES


def filter_to_changed(worklist, changed_files) -> list:
    """Keep only divergences whose file the diff actually changed."""
    cf = set(changed_files)
    return [w for w in worklist if w.get("file") in cf]


def gate_verdict(diff_worklist) -> dict:
    """Block only on grounded divergences in the diff; warn on the rest."""
    grounded = [w for w in diff_worklist if is_grounded(w.get("severity"))]
    advisory = [w for w in diff_worklist if not is_grounded(w.get("severity"))]
    return {"blocked": len(grounded) > 0, "grounded": grounded, "advisory": advisory}


def _changed_files(repo: Path, base: str) -> list:
    """Files changed on HEAD since the merge-base with `base` (PR semantics)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "diff", "--name-only", f"{base}...HEAD"],
            capture_output=True, text=True, timeout=60,
        )
        return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


def compute_integrity(repo, diff_base=None) -> dict:
    repo = Path(repo).resolve()
    archie = repo / ".archie"
    has_baseline = archie.is_dir()

    blueprint = _read_json(archie / "blueprint.json") or {}
    findings_store = _read_json(archie / "findings.json") or {}
    health = _read_json(archie / "health.json") or {}
    accepted = _accepted_rule_ids(archie)
    rules_idx = _rules_index(archie)

    # Reconciliation: open (unreconciled) violations from check_rules.
    cr = _run_check_rules(repo)
    violations = cr.get("violations") or []
    open_violations = [v for v in violations if v.get("rule_id") not in accepted]

    # Size for normalization: prefer health total_loc, else a quick count.
    loc = health.get("total_loc")
    if not isinstance(loc, (int, float)) or loc <= 0:
        loc = _count_loc(repo)
    kloc = max(loc / 1000.0, 0.001)

    open_findings = [f for f in (findings_store.get("findings") or [])
                     if isinstance(f, dict) and f.get("status", "open") != "resolved"]

    reconciliation = scoring.derive_reconciliation(open_violations, kloc)
    coverage, coverage_measured = scoring.derive_coverage(blueprint)
    burndown = scoring.derive_burndown(open_findings, kloc)
    # Freshness (v0): drops only when there are pending, unfolded amendments.
    freshness = 90.0 if accepted else 100.0

    comp = scoring.composite(reconciliation, coverage, burndown, freshness, coverage_measured)

    # Worklist: enrich each open violation with its rule's kind/why.
    worklist = []
    for v in open_violations:
        rule = rules_idx.get(v.get("rule_id"), {})
        worklist.append({
            "file": v.get("file", "?"),
            "line": v.get("line", 0),
            "rule_id": v.get("rule_id", "?"),
            "severity": v.get("severity", "info"),
            "kind": rule.get("kind") or rule.get("severity_class") or "rule",
            # Prefer the rule's plain-English description over the raw regex match.
            "message": rule.get("description") or v.get("rule_description") or v.get("message", ""),
        })
    worklist.sort(key=lambda w: (scoring.VIOLATION_SEVERITY_WEIGHT.get(w["severity"], 0) * -1,
                                 w["file"], w["line"]))

    domain = scoring._law_list(blueprint, "domain_invariants")
    derived = scoring._law_list(blueprint, "derived_invariants")
    unenforced = scoring._law_list(blueprint, "unenforced_invariants")
    total_laws = len(domain) + len(derived) + len(unenforced)
    enforced_laws = sum(1 for law in (domain + derived) if scoring._is_enforced(law))

    # Measurable only if there is a contract to measure against. A bare repo
    # (no rules, no laws) is unmeasurable -> AIS "n/a", never a free 100.
    measurable = has_baseline and (bool(rules_idx) or total_laws > 0)
    result = {
        "has_baseline": has_baseline,
        "measurable": measurable,
        "ais": comp["ais"] if measurable else None,
        "grade": comp["grade"] if measurable else None,
        "body": comp["body"], "ceiling": comp["ceiling"],
        "axes": {"reconciliation": reconciliation, "coverage": coverage,
                 "burndown": burndown, "freshness": freshness},
        "coverage_measured": coverage_measured,
        "open_divergences": len(worklist),
        "worklist": worklist,
        "protected_laws": {"enforced": enforced_laws, "total": total_laws,
                           "unguarded": _unguarded_laws(blueprint)},
        "hygiene": {k: health.get(k) for k in ("erosion", "gini", "top20_share", "verbosity")
                    if health.get(k) is not None},
        "loc": int(loc),
    }

    if diff_base:
        changed = _changed_files(repo, diff_base)
        diff_wl = filter_to_changed(worklist, changed)
        verdict = gate_verdict(diff_wl)
        result["diff"] = {
            "base": diff_base,
            "changed_files": len(changed),
            "worklist": diff_wl,
            "blocked": verdict["blocked"],
            "grounded": verdict["grounded"],
            "advisory": verdict["advisory"],
        }
    return result


def _git_head(repo: Path):
    try:
        p = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return p.stdout.strip() or None
    except Exception:
        return None


def write_baseline(repo, result) -> dict:
    """Persist the committed baseline: .archie/score.json + append score_history.json.

    The only timestamp is in the history entry (for trend display) — never in the
    score math, which stays a pure function of the commit + artifacts.
    """
    repo = Path(repo).resolve()
    archie = repo / ".archie"
    archie.mkdir(parents=True, exist_ok=True)
    base_sha = _git_head(repo)
    payload = {
        "score_version": SCORE_VERSION,
        "base_sha": base_sha,
        "ais": result["ais"], "grade": result["grade"],
        "body": result["body"], "ceiling": result["ceiling"],
        "axes": result["axes"], "coverage_measured": result["coverage_measured"],
        "open_divergences": result["open_divergences"],
        "worklist": result["worklist"],
        "protected_laws": result["protected_laws"],
        "hygiene": result["hygiene"],
        "explanation": explain(result),
    }
    (archie / "score.json").write_text(json.dumps(payload, indent=2) + "\n")

    hist_path = archie / "score_history.json"
    hist = _read_json(hist_path)
    if not isinstance(hist, list):
        hist = []
    hist.append({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "score_version": SCORE_VERSION, "base_sha": base_sha,
        "ais": result["ais"], "grade": result["grade"],
        "axes": result["axes"], "open_divergences": result["open_divergences"],
    })
    hist_path.write_text(json.dumps(hist, indent=2) + "\n")
    return payload


def explain(r: dict) -> dict:
    """Human-readable context so users understand the number, not just see it.

    Returns {what, why, action, legend, state}. ``state`` is a machine flag
    (no_contract | capped | reconciled | drift) the surfaces can branch on.
    """
    what = ("Architecture Integrity measures how well the code upholds its documented "
            "contract — the decisions and product laws Archie recorded — not a quality "
            "grade. The worklist is the point; the number is only its roll-up.")
    action = ("Each open divergence is code that broke a documented rule. Resolve it two "
              "ways — fix the code, or accept it with /archie-sync (which evolves the "
              "contract). Only unresolved (open) divergences lower the score or block a PR.")
    legend = [
        "open divergence — code breaks a documented decision/law, unreconciled (fix or accept)",
        "protected laws N/M — product laws with active enforcement / total identified",
        "hygiene — generic complexity signals, informational only (never affects the score)",
    ]
    pl = r.get("protected_laws", {"enforced": 0, "total": 0})
    if not r.get("measurable", True):
        state = "no_contract"
        why = ("No contract has been recorded for this repo yet, so there is nothing to "
               "measure against — run /archie-deep-scan to establish the baseline.")
    elif r["ceiling"] < r["body"] - 0.5:
        state = "capped"
        unguarded = max(pl["total"] - pl["enforced"], 0)
        why = (f"Headline capped at {r['grade']} ({r['ais']}) by the correctness axes: "
               f"{r['open_divergences']} open divergence(s) and {unguarded} unguarded "
               f"law(s) hold it down — clean code elsewhere (body {r['body']}) can't lift it.")
    elif r["open_divergences"] == 0:
        state = "reconciled"
        tail = (f", {pl['enforced']}/{pl['total']} laws guarded" if r.get("coverage_measured") else "")
        why = f"Code and contract agree: 0 open divergences{tail}."
    else:
        state = "drift"
        why = (f"{r['open_divergences']} open divergence(s) against the contract — "
               "the worklist shows each one to fix or accept.")
    return {"what": what, "why": why, "action": action, "legend": legend, "state": state}


def _context_block(r: dict) -> list:
    """The 'What this means' footer shared by the terminal views."""
    ex = explain(r)
    return ["", "What this means", f"  {ex['what']}", f"  {ex['why']}", f"  {ex['action']}"]


def render_pr(r: dict) -> str:
    """GitHub-flavored markdown for the PR comment — verdict + worklist + context."""
    ex = explain(r)
    d = r.get("diff")
    md = []
    if d:
        status = "BLOCK ❌" if d["blocked"] else "PASS ✅"
        md += [f"## 📐 Architecture Integrity — {status}", "",
               f"**Diff vs `{d['base']}`** · {d['changed_files']} files changed · "
               f"**{len(d['grounded'])} grounded divergence(s) in the diff**", "",
               "> Checks whether this change upholds the repo's documented contract "
               "(decisions + product laws) — not code style. Only *open grounded "
               "divergences in your diff* can block; the integrity number never blocks."]
        if d["grounded"]:
            md += ["", "**Fix or accept (via `/archie-sync`) to merge:**"]
            md += [f"- ❌ `{w['file']}:{w['line']}` — {w['message']} _[{w['kind']}]_"
                   for w in d["grounded"]]
        md += ["", f"_Context: AIS **{r['ais']} ({r['grade']})**, "
               f"{r['open_divergences']} divergence(s) total in the repo (pre-existing "
               "ones elsewhere don't block this PR)._"]
    else:
        md += [f"## 📐 Architecture Integrity — AIS {r['ais']} ({r['grade']})", "",
               f"> {ex['what']}", "",
               f"**{r['open_divergences']} open divergence(s)** · "
               f"**Protected laws {r['protected_laws']['enforced']}/{r['protected_laws']['total']}**"]
        md += [f"- ❌ `{w['file']}:{w['line']}` — {w['message']} _[{w['kind']}]_"
               for w in r["worklist"][:10]]
    md += ["", "<details><summary>How to read this</summary>", ""]
    md += [f"- {item}" for item in ex["legend"]]
    md += ["", f"_{ex['action']}_", "</details>"]
    return "\n".join(md)


def render_gate(r: dict) -> str:
    d = r["diff"]
    status = "BLOCK ✗" if d["blocked"] else "PASS ✓"
    lines = [f"Archie Gate · diff vs {d['base']}   →   {status}",
             f"  {d['changed_files']} files changed"]
    if not d["worklist"]:
        lines.append("  0 open divergences in the diff")
    else:
        if d["grounded"]:
            lines.append(f"  {len(d['grounded'])} grounded divergence(s) — fix or accept to merge:")
            for w in d["grounded"]:
                lines.append(f"    ✗ {w['file']}:{w['line']}  {w['message'][:46]} [{w['kind']}]")
        if d["advisory"]:
            lines.append(f"  {len(d['advisory'])} advisory (warn, non-blocking)")
    lines.append(f"  context: AIS {r['ais']} ({r['grade']}) · "
                 f"{r['open_divergences']} divergence(s) total in repo")
    lines += _context_block(r)
    return "\n".join(lines)


def render(r: dict) -> str:
    if r.get("diff"):
        return render_gate(r)
    lines = []
    cov = (f"{r['protected_laws']['enforced']}/{r['protected_laws']['total']}"
           if r["coverage_measured"] else "n/a")
    if r.get("measurable", True) and r["ais"] is not None:
        lines.append(f"Architecture Integrity   AIS {r['ais']} ({r['grade']})"
                     f"   body {r['body']} · ceiling {r['ceiling']}")
    else:
        lines.append("Architecture Integrity   AIS n/a — no contract to measure "
                     "against (run /archie-deep-scan first)")
    if not r["has_baseline"]:
        lines.append("  (!) no .archie/ baseline found")
    lines.append("")

    n = r["open_divergences"]
    if n == 0:
        lines.append("0 open divergences — contract and code are reconciled ✓")
    else:
        lines.append(f"{n} open divergence{'s' if n != 1 else ''} — fix or accept to clear")
        for w in r["worklist"]:
            loc = f"{w['file']}:{w['line']}"
            lines.append(f"  ✗ {loc:<32} {w['message'][:48]:<48} [{w['kind']}]")

    pl = r["protected_laws"]
    if r["coverage_measured"]:
        gap = (f"   unguarded: {', '.join(pl['unguarded'][:4])}" if pl["unguarded"] else "")
        lines.append(f"Protected laws  {cov}{gap}")
    else:
        lines.append("Protected laws  n/a   (no product laws detected)")

    if r["hygiene"]:
        h = r["hygiene"]
        bits = []
        if "erosion" in h:
            bits.append(f"erosion {h['erosion']}")
        if "verbosity" in h:
            bits.append(f"dup {h['verbosity']}")
        if "gini" in h:
            bits.append(f"gini {h['gini']}")
        lines.append(f"hygiene (info)  {' · '.join(bits)}")
    lines += _context_block(r)
    return "\n".join(lines)


def main(argv) -> int:
    as_json = "--json" in argv
    diff_base = None
    if "--diff" in argv:
        i = argv.index("--diff")
        if i + 1 < len(argv):
            diff_base = argv[i + 1]
    positional = [a for a in argv if not a.startswith("--") and a != diff_base]
    if not positional:
        print("Usage: python3 score.py /path/to/repo [--diff <base-ref>] [--json]",
              file=sys.stderr)
        return 1
    result = compute_integrity(positional[0], diff_base=diff_base)
    if "--write" in argv:
        write_baseline(positional[0], result)
    if as_json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif "--pr" in argv:
        print(render_pr(result))
    else:
        print(render(result))
    # CI gate: non-zero exit only when the diff introduces a grounded (blocking)
    # divergence. The score itself never gates — only open grounded violations do.
    if result.get("diff", {}).get("blocked"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
