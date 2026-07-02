"""PR-gate delivery review: intake + full A/B/C reconciliation + verdict comment.
Reuses intent_review.post_or_update_comment for the upsert. Diffing, intent, and
gating come from the shared core.
"""
from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)

_OVERRIDE_LABEL = "archie-review"
_SKIP_LABEL = "archie-skip"

# Default cap on changed files before a PR is considered too large to review.
MAX_FILES = 75
# Bound the diff payload sent to the LLM (chars) so a huge PR can't blow the budget.
MAX_DIFF_CHARS = 60000

# Zero-width space used to neutralize leading @ in model-derived text.
_ZWS = "​"


def _sanitize(text: object) -> str:
    """Sanitize a model-derived field before embedding in a Markdown comment.

    - Coerces to str.
    - HTML-escapes <, >, & so injected HTML comment markers (<!--/-->) become
      harmless entities (&lt;!-- / --&gt;) and raw HTML tags are neutralized.
    - Collapses newlines/carriage returns to spaces so a field cannot inject a
      second Markdown block / fake verdict heading on its own line.
    - Neutralizes @ ANYWHERE (not just token-start) to prevent live GitHub
      @mention notifications (e.g. "(@everyone)", ".@here").
    """
    s = html.escape(str(text) if text is not None else "")
    # Collapse newlines/CRs to spaces — no field may open a new Markdown line.
    s = s.replace("\r", " ").replace("\n", " ")
    # Neutralize EVERY @ so no live mention can survive regardless of position.
    s = s.replace("@", "@" + _ZWS)
    return s


def should_review(pr_meta: dict, max_files: int) -> tuple[bool, str]:
    """Determine if a PR should receive a delivery review.

    Returns (eligible: bool, reason: str).

    Priority order:
    1. Override label forces True even for bots.
    2. Bot author → False.
    3. Skip label → False.
    4. Too many changed files → False.
    5. Otherwise → True.
    """
    labels = pr_meta.get("labels") or []
    if _OVERRIDE_LABEL in labels:
        return True, "override label"
    if str(pr_meta.get("author", "")).endswith("[bot]"):
        return False, "bot author"
    if _SKIP_LABEL in labels:
        return False, "skip label"
    if int(pr_meta.get("changed_files") or 0) > max_files:
        return False, "too many files"
    return True, "eligible"


def render_verdict(verdict: dict, confirmed: list[dict], spec=None) -> str:
    """Render a Markdown delivery verdict comment.

    Args:
        verdict: dict with keys intent_completeness, breaks, conflicts, unknown.
        confirmed: list of confirmed finding dicts with kind, problem_statement, anchor.
        spec: optional intent spec dict with source, confidence, confirmed, acceptance_criteria.

    Returns:
        Markdown string with HTML marker comment for upsert.
    """
    spec = spec or {}
    crit = spec.get("acceptance_criteria") or []
    unmet_ids = {f.get("criterion_id") for f in confirmed if f.get("kind") in ("intent_unmet", "intent_partial")}
    trust = "human-confirmed" if spec.get("confirmed") else "unconfirmed (auto-synthesized — lower trust)"
    lines = ["<!-- archie-delivery-review -->", "## Archie delivery review", ""]
    lines.append(f"> Grading against `.archie/intent.json` · source: **{_sanitize(spec.get('source', '?'))}** "
                 f"· confidence: **{_sanitize(spec.get('confidence', '?'))}** · {trust}")
    lines.append("")
    unknown = verdict.get("unknown", 0)
    lines.append(f"**Built the intent?** {verdict.get('intent_completeness', '?')} criteria met"
                 + (f" ({unknown} unknown)" if unknown else "") + ".")
    for c in crit:
        mark = "❌" if c.get("id") in unmet_ids else "✅"
        lines.append(f"- {mark} {_sanitize(c.get('id'))} — {_sanitize(c.get('text', ''))}")
    lines.append("")
    lines.append(f"**Broke anything?** {verdict.get('breaks', 0)} break(s), {verdict.get('conflicts', 0)} conflict(s).")
    for f in confirmed:
        if f.get("kind") in ("intent_unmet", "intent_partial"):
            continue
        a = f.get("anchor", {}) or {}
        reviewer = _sanitize(str(f.get("source", "")).split(":")[-1])
        lines.append(f"- `{_sanitize(f.get('kind', ''))}` {_sanitize(f.get('problem_statement', ''))} "
                     f"({_sanitize(a.get('file', ''))}:{_sanitize(str(a.get('line', '')))}) · _{reviewer}_")
    lines.append("")
    lines.append("_Intent wrong? Edit `.archie/intent.json` (or re-run synthesize) and push — this comment updates._")
    return "\n".join(lines)


def _load_pr_meta_from_event(event_path):
    """Read the GitHub event payload -> PR metadata dict.

    Returns {author, changed_files, labels, number, base_ref, base_sha, head_sha}.
    Never raises: on any error returns an empty-ish dict so the caller degrades
    gracefully (no PR context -> nothing to review).
    """
    meta = {"author": "", "changed_files": 0, "labels": [], "number": None,
            "base_ref": "", "base_sha": "", "head_sha": "", "head_ref": "",
            "title": "", "body": ""}
    if not event_path or not Path(event_path).exists():
        return meta
    try:
        event = json.loads(Path(event_path).read_text())
    except Exception:
        return meta
    pr = event.get("pull_request") or {}
    if isinstance(pr, dict):
        meta["number"] = pr.get("number")
        meta["changed_files"] = pr.get("changed_files") or 0
        user = pr.get("user") or {}
        meta["author"] = str(user.get("login", "")) if isinstance(user, dict) else ""
        base = pr.get("base") or {}
        head = pr.get("head") or {}
        meta["base_ref"] = str(base.get("ref", "") or "")
        meta["base_sha"] = str(base.get("sha", "") or "")
        meta["head_sha"] = str(head.get("sha", "") or "")
        meta["head_ref"] = str(head.get("ref", "") or "")
        meta["title"] = str(pr.get("title", "") or "")
        meta["body"] = str(pr.get("body", "") or "")
        labels = pr.get("labels") or []
        meta["labels"] = [l.get("name") for l in labels
                          if isinstance(l, dict) and l.get("name")]
    return meta


def assemble_pr_intent(root, pr_meta, env, *, run=None):
    """Merge intent from committed .archie/intent.json ⊕ PR title/body.
    resolve() runs ONLY if the merged spec still has no acceptance_criteria."""
    import sys as _sys
    _p = str(Path(__file__).parent)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
    from intent import (load_committed_intent, merge_specs, normalize,
                        resolve, ticket_ids_from)  # noqa: E402

    file_spec = load_committed_intent(root)
    title = pr_meta.get("title") or ""
    body = pr_meta.get("body") or env.get("ARCHIE_PR_BODY", "")
    branch = pr_meta.get("head_ref") or ""
    pr_text = (title + "\n\n" + body).strip()
    tickets = ticket_ids_from(branch, pr_text, [])
    pr_spec = normalize(pr_text, "pr_body", tickets) if pr_text else None

    spec = merge_specs(file_spec, pr_spec)
    if not spec.get("acceptance_criteria") and spec.get("raw"):
        try:
            spec = resolve(spec, run=run)
        except Exception as e:
            print(f"[archie] intent resolve failed ({e})")
    return spec


def run_pr_gate(root=".", env=None):
    """Compose the PR gate: intake -> diff -> resolve intent -> reconcile (A/B/C)
    + behavioral -> gate -> verdict -> comment.

    NON-BLOCKING by contract: every external step (git, LLM, GitHub API) is guarded,
    a failure prints a line and continues, and the function NEVER raises. Returns a
    small status dict for callers/tests.
    """
    env = env if env is not None else os.environ
    root = Path(root)
    status = {"reviewed": False, "reason": "", "posted": False, "verdict": None}

    # 1. Read PR context from the GitHub event payload.
    pr_meta = _load_pr_meta_from_event(env.get("GITHUB_EVENT_PATH", ""))

    # 2. Intake gate — skip bots / skip-label / too-many-files (override-label wins).
    ok, reason = should_review(pr_meta, MAX_FILES)
    status["reason"] = reason
    if not ok:
        print(f"[archie] delivery review skipped ({reason})")
        return status
    if not pr_meta.get("number"):
        print("[archie] delivery review skipped (no PR context)")
        status["reason"] = "no pr context"
        return status

    # Hands-off fallback: if nobody synthesized intent but events were captured, do it now (blind).
    try:
        if not (Path(root) / ".archie" / "intent.json").exists():
            import sys as _sys
            _pp = str(Path(__file__).parent)
            if _pp not in _sys.path:
                _sys.path.insert(0, _pp)
            from intent_synthesize import synthesize
            synthesize(root)
    except Exception as e:
        print(f"[archie] intent auto-synthesize skipped ({e})")

    # 3. Diff basis — provider base SHA when present, else detect. Bounded diff text.
    diff_text, changed, changed_lines = "", [], {}
    try:
        from diff_basis import detect_base, changed_files_result, parse_hunk_added_lines
        base = pr_meta.get("base_sha") or pr_meta.get("base_ref") or detect_base(root)
        res = changed_files_result(root, base)
        changed = res.get("files", []) if res.get("ok") else []
        try:
            from intent_review import run_git
            _, out, _ = run_git(root, "diff", base, "--")
            diff_text = (out or "")[:MAX_DIFF_CHARS]
            # changed-line map: parse a -U0 diff into the REAL added-line numbers per
            # file so the editor gate keeps line-anchored findings on changed lines
            # (instead of dropping all of them as anchor_unchanged). On any failure
            # fall back to {} — the gate then skips the anchor check (findings survive).
            try:
                import subprocess
                r = subprocess.run(
                    ["git", "-C", str(root), "diff", "-U0", base, "--"],
                    capture_output=True, text=True, timeout=30,
                )
                changed_lines = (parse_hunk_added_lines(r.stdout)
                                 if r.returncode == 0 else {})
            except Exception as e:
                print(f"[archie] changed-line parse failed ({e})")
                changed_lines = {}
        except Exception as e:
            print(f"[archie] diff read failed ({e})")
    except Exception as e:
        print(f"[archie] diff basis failed ({e})")

    # 4. Assemble intent: committed .archie/intent.json ⊕ PR title/body.
    try:
        spec = assemble_pr_intent(root, pr_meta, env)
    except Exception as e:
        print(f"[archie] intent assembly failed ({e})")
        spec = {"acceptance_criteria": [], "goals": [], "confidence": "low"}

    # 5. Load the blueprint (for edge-C invariants + behavioral blast radius).
    blueprint, import_graph = {}, {}
    try:
        bp_path = root / ".archie" / "blueprint.json"
        if bp_path.exists():
            blueprint = json.loads(bp_path.read_text()) or {}
        scan_path = root / ".archie" / "scan.json"
        if scan_path.exists():
            import_graph = (json.loads(scan_path.read_text()) or {}).get("import_graph", {})
    except Exception as e:
        print(f"[archie] blueprint load failed ({e})")

    # 6. Run the reviewers — each guarded so one failure never blocks the rest.
    raw = []
    try:
        from reconcile import review_edge_a
        raw += review_edge_a(root, spec, diff_text)
    except Exception as e:
        print(f"[archie] edge-A skipped ({e})")
    try:
        from behavioral_review import review as behavioral_review_run
        raw += behavioral_review_run(root, diff_text, import_graph, changed, intent=spec)
    except Exception as e:
        print(f"[archie] behavioral review skipped ({e})")
    if spec.get("acceptance_criteria") or spec.get("goals"):
        try:
            from reconcile import review_edge_c
            raw += review_edge_c(root, spec, (blueprint.get("domain_invariants") or []))
        except Exception as e:
            print(f"[archie] edge-C skipped ({e})")
    # Conformance (edge B): did the DIFF break a standing invariant/decision? Uses the
    # selector's routing (touched_context) to pick the SPECIFIC items the change touched.
    try:
        from selector import touched_context
        from reconcile import review_conformance
        ctx = touched_context(blueprint, changed)
        raw += review_conformance(root, diff_text, ctx["invariants"], ctx["decisions"], intent=spec)
    except Exception as e:
        print(f"[archie] conformance skipped ({e})")

    # 7. Editor gate + aggregate verdict.
    confirmed = []
    verdict = {"intent_completeness": "0/0", "breaks": 0, "conflicts": 0, "gate_signal": 1.0}
    try:
        from editor_gate import gate
        from reconcile import aggregate_verdict
        store = []
        fp = root / ".archie" / "findings.json"
        if fp.exists():
            try:
                store = json.loads(fp.read_text()).get("findings", [])
            except Exception:
                store = []
        floors = {}
        cl = changed_lines or None
        result = gate(raw, store, changed_lines=cl, floors=floors)
        confirmed = result.get("confirmed", [])
        verdict = aggregate_verdict(spec, confirmed)
    except Exception as e:
        print(f"[archie] gate/verdict failed ({e})")

    status["reviewed"] = True
    status["verdict"] = verdict

    # 8. Render + publish. Fork PRs (no token) print the verdict instead of posting.
    # A render/post failure must never abort the review (exit 0 by contract).
    try:
        body = render_verdict(verdict, confirmed, spec)
        token = env.get("GITHUB_TOKEN", "").strip()
        repo_full = env.get("GITHUB_REPOSITORY", "")
        number = pr_meta.get("number")
        if token and number and "/" in repo_full:
            owner, repo = repo_full.split("/", 1)
            try:
                from intent_review import post_or_update_comment
                post_or_update_comment(owner, repo, number, body, token)
                status["posted"] = True
            except Exception as e:
                print(f"[archie] could not post comment ({e})")
                print(body)
        else:
            print("[archie] no GITHUB_TOKEN / PR — printing verdict:\n" + body)
    except Exception as e:
        print(f"[archie] render/publish failed ({e})")

    return status


if __name__ == "__main__":
    try:
        run_pr_gate(os.getcwd(), os.environ)
    except Exception as e:
        print(f"[archie] delivery review skipped (error: {e})")
    # Non-blocking by design: always exit 0.
    sys.exit(0)
