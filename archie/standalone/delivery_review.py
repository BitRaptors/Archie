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


def render_verdict(verdict: dict, confirmed: list[dict], spec=None, acked=None, stale_acks=None) -> str:
    """Render a Markdown delivery verdict comment.

    Args:
        verdict: dict with keys intent_completeness, breaks, conflicts, unknown.
        confirmed: list of confirmed finding dicts with kind, problem_statement, anchor.
        spec: optional intent spec dict with source, confidence, confirmed, acceptance_criteria.
        acked: optional list of (override_entry, [findings]) tuples — human-acknowledged
            overrides, excluded from the break count, rendered in their own section.
        stale_acks: optional list of override entries whose ruled-on violation was not
            observed this run — flagged so a reverted change doesn't leave a dangling ack.

    Returns:
        Markdown string with HTML marker comment for upsert.
    """
    spec = spec or {}
    crit = spec.get("acceptance_criteria") or []
    # criterion_id is model-shaped: may be a scalar OR a list (a set comprehension
    # over raw values raised unhashable-type and killed the render).
    unmet_ids = set()
    for f in confirmed:
        if f.get("kind") in ("intent_unmet", "intent_partial"):
            cid = f.get("criterion_id")
            if isinstance(cid, (list, tuple)):
                unmet_ids.update(str(c) for c in cid if c)
            elif cid:
                unmet_ids.add(str(cid))
    trust = "human-confirmed" if spec.get("confirmed") else "unconfirmed (auto-synthesized — lower trust)"
    engine_failed = bool(spec.get("review_engine_failed"))
    lines = ["<!-- archie-delivery-review -->", "## Archie delivery review", ""]
    if engine_failed:
        lines.append("> 🛑 **REVIEW ENGINE FAILED — no code review was performed.** "
                     "Do NOT treat this comment as a green verdict. Check the workflow "
                     "logs for `[archie] review core failed`.")
        lines.append("")
    lines.append(f"> Grading against the task story · source: **{_sanitize(spec.get('source', '?'))}** "
                 f"· confidence: **{_sanitize(spec.get('confidence', '?'))}** · {trust}")
    lines.append("")
    if spec.get("diff_truncated"):
        lines.append("> ⚠️ diff was truncated to the review budget — some files may be unreviewed.")
        lines.append("")
    story = (spec.get("story") or "").strip()
    if story:
        lines.append("<details><summary>Task story</summary>\n\n" + _sanitize(story) + "\n\n</details>")
        lines.append("")
    unknown = verdict.get("unknown", 0)
    if engine_failed:
        lines.append("**Built the intent?** not assessed — the review engine failed before grading.")
    else:
        lines.append(f"**Built the intent?** {verdict.get('intent_completeness', '?')} criteria met"
                     + (f" ({unknown} unknown)" if unknown else "") + ".")
        for c in crit:
            mark = "❌" if str(c.get("id")) in unmet_ids else "✅"
            src = _sanitize(((c.get("from") or {}).get("quote") or ""))
            suffix = f"  ·  _from: {src[:70]}_" if src else ""
            lines.append(f"- {mark} {_sanitize(c.get('id'))} — {_sanitize(c.get('text', ''))}{suffix}")
    try:
        from reconcile import is_advisory_finding
    except Exception:
        def is_advisory_finding(f):
            c = f.get("confidence")
            return isinstance(c, (int, float)) and c < 0.6
    break_kinds = ("conformance_break", "behavioral_break")

    def _render_finding(f):
        a = f.get("anchor", {}) or {}
        reviewer = _sanitize(str(f.get("source", "")).split(":")[-1])
        return (f"- `{_sanitize(f.get('kind', ''))}` {_sanitize(f.get('problem_statement', ''))} "
                f"({_sanitize(a.get('file', ''))}:{_sanitize(str(a.get('line', '')))}) · _{reviewer}_")

    lines.append("")
    if engine_failed:
        lines.append("**Broke anything?** not assessed — no reviewer ran.")
    else:
        lines.append(f"**Broke anything?** {verdict.get('breaks', 0)} break(s), {verdict.get('conflicts', 0)} conflict(s).")
    possible = []
    for f in confirmed:
        if f.get("kind") in ("intent_unmet", "intent_partial"):
            continue
        if f.get("kind") in break_kinds and is_advisory_finding(f):
            possible.append(f)   # advisory — rendered in its own section below
            continue
        lines.append(_render_finding(f))

    # Independent code-review lane: genuine coding issues the reviewer surfaced that
    # aren't confident enough to call a "break" — shown so they aren't silently lost.
    if possible:
        lines.append("")
        lines.append(f"**Possible issues** ({len(possible)} — unverified, lower confidence; worth a look):")
        for f in possible:
            lines.append(_render_finding(f))

    if acked:
        lines.append("")
        lines.append(f"**⚠️ Acknowledged overrides** ({len(acked)} — user-authorized, "
                     "not counted as breaks; merging ratifies the amendment):")
        for entry, fs in acked:
            lines.append(f"- `{_sanitize(entry.get('rule_id', '?'))}` — "
                         f"{_sanitize(entry.get('reason', ''))} · authorized by "
                         f"**{_sanitize(entry.get('authorized_by', '?'))}** on "
                         f"{_sanitize(str(entry.get('created_at', ''))[:10])}")
            for f in fs:
                lines.append("  " + _render_finding(f))
    if stale_acks:
        lines.append("")
        lines.append("**Stale overrides** (no matching violation observed this run — if the "
                     "change was reverted, remove the entry from `.archie/overrides.json`):")
        for e in stale_acks:
            lines.append(f"- `{_sanitize(e.get('rule_id', '?'))}` — {_sanitize(e.get('reason', ''))}")

    lines.append("")
    lines.append("_Story wrong? Edit the task story (or re-run `archie imprint`) and push — this comment updates._")
    return "\n".join(lines)


def partition_for_verdict(root, confirmed):
    """Split confirmed findings by human ruling (overrides.partition). Degrades
    to (confirmed, [], []) when the overrides module/file is absent — the exit-0
    contract must survive a missing ledger."""
    try:
        import overrides as _ov
        act = _ov.active(root)
        if not act:
            return confirmed, [], []
        return _ov.partition(confirmed, act, root=root)
    except Exception:
        return confirmed, [], []


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
    """Merge intent from current task story ⊕ PR title/body.
    Falls back to PR-only intent when there is no active story.
    resolve() runs ONLY if the merged spec still has no acceptance_criteria."""
    import sys as _sys
    _p = str(Path(__file__).parent)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
    from intent import (merge_specs, normalize,  # noqa: E402
                        resolve, ticket_ids_from)
    import story_store  # noqa: E402

    # Resolve the branch: PR meta first, then env vars used by CI providers.
    branch = (pr_meta.get("head_ref")
              or os.environ.get("ARCHIE_BRANCH")
              or os.environ.get("GITHUB_HEAD_REF")
              or "")

    story = story_store.current_story(root, branch)
    committed = {"acceptance_criteria": [], "non_goals": [], "source": "sync",
                 "confirmed": False, "story": ""}
    if story:
        committed["acceptance_criteria"] = [
            {"id": f.get("id"), "text": f.get("text", ""), "from": f.get("from")}
            for f in story["facts"]
        ]
        committed["non_goals"] = story.get("non_goals") or []
        committed["confirmed"] = bool(story["meta"].get("confirmed"))
        committed["story"] = story.get("story") or ""

    title = pr_meta.get("title") or ""
    body = pr_meta.get("body") or env.get("ARCHIE_PR_BODY", "")
    pr_text = (title + "\n\n" + body).strip()
    tickets = ticket_ids_from(branch, pr_text, [])
    pr_spec = normalize(pr_text, "pr_body", tickets) if pr_text else None

    # Use committed story spec as the base; merge PR title/body on top.
    file_spec = committed if (committed["acceptance_criteria"] or committed["story"]) else None
    spec = merge_specs(file_spec, pr_spec)
    if not spec.get("acceptance_criteria") and spec.get("raw"):
        try:
            spec = resolve(spec, run=run)
        except Exception as e:
            print(f"[archie] intent resolve failed ({e})")
    # Propagate story fields that merge_specs doesn't know about.
    if committed["story"] and not spec.get("story"):
        spec["story"] = committed["story"]
    if committed["non_goals"] and not spec.get("non_goals"):
        spec["non_goals"] = committed["non_goals"]
    # merge_specs rebuilds criteria as {id, text} and drops per-fact provenance.
    # Re-attach `from` by matching on normalized text so the verdict can render it.
    _prov = {}
    for _c in (committed.get("acceptance_criteria") or []):
        if _c.get("from"):
            _prov[(_c.get("text") or "").strip().lower()] = _c["from"]
    for _c in (spec.get("acceptance_criteria") or []):
        _k = (_c.get("text") or "").strip().lower()
        if _k in _prov and not _c.get("from"):
            _c["from"] = _prov[_k]
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

    # Hands-off fallback: if no current story exists but turns were captured, imprint now (blind).
    try:
        import story_store, story_synthesize
        import os as _os
        from datetime import datetime as _dt, timezone as _tz
        _branch = (pr_meta.get("head_ref") or _os.environ.get("ARCHIE_BRANCH")
                   or _os.environ.get("GITHUB_HEAD_REF") or "")
        if story_store.current_story(root, _branch) is None:
            _sid = _os.environ.get("CLAUDE_SESSION_ID") or _os.environ.get("ARCHIE_SESSION_ID") or "session"
            _ts = _dt.now(_tz.utc).strftime("%Y-%m-%dT%H%M%S")
            story_synthesize.imprint(root, _branch, _sid, _ts)
    except Exception as e:
        print(f"[archie] story auto-imprint skipped ({e})")

    # 3. Diff basis — provider base SHA when present, else detect. Bounded diff text.
    diff_text, changed, changed_lines, spec_truncated = "", [], {}, False
    try:
        from diff_basis import detect_base, changed_files_result, parse_hunk_added_lines, review_pathspec
        base = pr_meta.get("base_sha") or pr_meta.get("base_ref") or detect_base(root)
        res = changed_files_result(root, base)
        changed = res.get("files", []) if res.get("ok") else []
        try:
            from intent_review import run_git
            _, out, _ = run_git(root, "diff", base, "--", *review_pathspec())
            diff_text = (out or "")[:MAX_DIFF_CHARS]
            spec_truncated = len(out or "") > MAX_DIFF_CHARS
            # changed-line map: parse a -U0 diff into the REAL added-line numbers per
            # file so the editor gate keeps line-anchored findings on changed lines
            # (instead of dropping all of them as anchor_unchanged). On any failure
            # fall back to {} — the gate then skips the anchor check (findings survive).
            try:
                import subprocess
                r = subprocess.run(
                    ["git", "-C", str(root), "diff", "-U0", base, "--", *review_pathspec()],
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

    # 4. Assemble intent: current task story ⊕ PR title/body.
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

    # 6. Run the reviewers via the shared core (evidence pack + parallel fan-out + merge).
    #    One core, shared with the local sync review (F3). Guarded — a core failure
    #    degrades to no findings, never aborts the gate — but it must be DISCLOSED:
    #    a crashed engine once rendered as a glowing 13/13, 0-break verdict (PR #17).
    raw = []
    engine_failed = False
    try:
        from review_core import run_review
        if spec_truncated:
            spec["diff_truncated"] = True
        raw = run_review(root, diff_text, changed, blueprint, import_graph, spec)
    except Exception as e:
        engine_failed = True
        print(f"[archie] review core failed ({e})")

    # 7. Editor gate + aggregate verdict.
    confirmed = []
    acked_over, stale_over = [], []
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
        # Advisory code-review kinds anchor file-level (LLM line numbers are imprecise)
        # and carry no confidence floor — surface what the reviewer finds, then split
        # by confidence at render time into breaks vs "possible issues".
        advisory = {"behavioral_break", "conformance_break"}
        floors = {k: 0.0 for k in advisory}
        cl = changed_lines or None
        result = gate(raw, store, changed_lines=cl, floors=floors, file_level_kinds=advisory)
        confirmed = result.get("confirmed", [])
        confirmed, acked_over, stale_over = partition_for_verdict(root, confirmed)
        verdict = aggregate_verdict(spec, confirmed)
    except Exception as e:
        # A gate/verdict crash silently discards every finding — that is an
        # engine failure for the reader's purposes (PR #17 rendered green this
        # way twice, through two different holes). Fail closed here too.
        engine_failed = True
        print(f"[archie] gate/verdict failed ({e})")

    # Fail CLOSED at render time: a dead engine must never present as a clean
    # review. "Silence = met" completeness and the stale-override sweep are both
    # meaningless when no reviewer ran — mark them not-assessed instead.
    if engine_failed:
        spec["review_engine_failed"] = True
        verdict["intent_completeness"] = "n/a"
        stale_over = []

    status["reviewed"] = not engine_failed
    status["verdict"] = verdict

    # 8. Render + publish. Fork PRs (no token) print the verdict instead of posting.
    # A render/post failure must never abort the review (exit 0 by contract).
    try:
        body = render_verdict(verdict, confirmed, spec, acked=acked_over, stale_acks=stale_over)
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
