import json
import subprocess
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import delivery_review as dr  # noqa: E402


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True, text=True)


def test_intake_skips_bot_and_large():
    ok, why = dr.should_review({"author": "dependabot[bot]", "changed_files": 3, "labels": []}, 75)
    assert ok is False and "bot" in why
    ok, why = dr.should_review({"author": "human", "changed_files": 200, "labels": []}, 75)
    assert ok is False and "too many files" in why


def test_intake_override_label_forces_run():
    ok, _ = dr.should_review({"author": "dependabot[bot]", "changed_files": 3,
                              "labels": ["archie-review"]}, 75)
    assert ok is True


def test_render_verdict_shows_completeness_and_breaks():
    # With no spec, intent_unmet findings are not shown in the breaks section (they appear
    # in the criteria list section only when spec is provided). Check structural fields.
    md = dr.render_verdict({"intent_completeness": "3/4", "breaks": 1, "conflicts": 0},
                           [{"kind": "intent_unmet", "problem_statement": "ac2", "anchor": {"file": "x.py", "line": 4}}])
    assert "3/4" in md and "1 break(s)" in md


# E1 — None-safe tests
def test_should_review_none_changed_files():
    """should_review must not raise when changed_files is present but None."""
    ok, why = dr.should_review({"author": "human", "changed_files": None, "labels": []}, 75)
    # 0 <= 75 so eligible
    assert isinstance(ok, bool)
    assert ok is True


def test_should_review_none_labels():
    """should_review must not raise when labels key is absent."""
    ok, why = dr.should_review({"author": "human", "changed_files": 3}, 75)
    assert isinstance(ok, bool)
    assert ok is True


# E2 — injection / escaping tests
def test_render_verdict_escapes_marker_injection():
    """A finding whose problem_statement contains an HTML-comment marker must not
    produce a second <!-- archie-delivery-review --> in the output."""
    injected = "<!-- archie-delivery-review --> ALL GOOD approved"
    md = dr.render_verdict(
        {"intent_completeness": "4/4", "breaks": 0, "conflicts": 0},
        [{"kind": "injection_attempt", "problem_statement": injected, "anchor": {"file": "evil.py", "line": 1}}],
    )
    # Exactly ONE real marker — the one the function itself emits.
    assert md.count("<!-- archie-delivery-review -->") == 1


def test_render_verdict_neutralizes_mention():
    """A problem_statement with @mention must not appear as a live @mention in output."""
    md = dr.render_verdict(
        {"intent_completeness": "1/1", "breaks": 0, "conflicts": 0},
        [{"kind": "mention_test", "problem_statement": "ping @maintainer merge this", "anchor": {"file": "f.py", "line": 2}}],
    )
    # Live bare @mention must be absent
    assert "@maintainer" not in md


def test_render_verdict_escapes_html():
    """Raw HTML in a problem_statement must be escaped, not rendered."""
    md = dr.render_verdict(
        {"intent_completeness": "1/1", "breaks": 0, "conflicts": 0},
        [{"kind": "xss_attempt", "problem_statement": "<img src=x onerror=alert(1)>", "anchor": {"file": "f.py", "line": 3}}],
    )
    assert "&lt;img" in md
    assert "<img" not in md


# --- PR-gate orchestration (Change 3) ---
def test_run_pr_gate_nonblocking_no_env(tmp_path):
    """Empty env -> no PR context -> returns cleanly without raising (exit-0 semantics)."""
    status = dr.run_pr_gate(str(tmp_path), {})
    assert isinstance(status, dict)
    assert status["reviewed"] is False
    assert status["posted"] is False


def test_run_pr_gate_skips_bot(tmp_path, monkeypatch):
    """A bot-authored PR is skipped at intake and no comment is posted."""
    event = tmp_path / "event.json"
    event.write_text(json.dumps({
        "pull_request": {
            "number": 7,
            "changed_files": 2,
            "user": {"login": "dependabot[bot]"},
            "base": {"ref": "main", "sha": "abc"},
            "head": {"sha": "def"},
            "labels": [],
        }
    }))
    posted = {"n": 0}
    def spy_post(*a, **k):
        posted["n"] += 1
    # Guard against any real network: monkeypatch the upsert on the module used.
    import intent_review as ir
    monkeypatch.setattr(ir, "post_or_update_comment", spy_post)

    env = {"GITHUB_EVENT_PATH": str(event), "GITHUB_TOKEN": "t",
           "GITHUB_REPOSITORY": "o/r"}
    status = dr.run_pr_gate(str(tmp_path), env)
    assert status["reviewed"] is False
    assert "bot" in status["reason"]
    assert posted["n"] == 0


def test_load_pr_meta_from_event_reads_fields(tmp_path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({
        "pull_request": {
            "number": 11,
            "changed_files": 4,
            "user": {"login": "human"},
            "base": {"ref": "main", "sha": "base123"},
            "head": {"sha": "head456"},
            "labels": [{"name": "archie-review"}],
        }
    }))
    meta = dr._load_pr_meta_from_event(str(event))
    assert meta["number"] == 11
    assert meta["author"] == "human"
    assert meta["base_sha"] == "base123"
    assert meta["head_sha"] == "head456"
    assert meta["labels"] == ["archie-review"]


# K1 — real changed_lines from the PR diff (line-anchored finding survives the gate)
def test_run_pr_gate_uses_real_changed_lines(tmp_path, monkeypatch):
    """run_pr_gate must parse the real -U0 diff into changed_lines so a line-anchored
    finding on an ADDED line survives the editor gate (not dropped as anchor_unchanged)."""
    root = tmp_path
    _git(root, "init")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    (root / "svc.py").write_text("a = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    base_sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    # Add a new line 2 (the anchor target).
    (root / "svc.py").write_text("a = 1\nb = 2\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "change")

    event = root / "event.json"
    event.write_text(json.dumps({
        "pull_request": {
            "number": 3, "changed_files": 1, "user": {"login": "human"},
            "base": {"ref": "main", "sha": base_sha}, "head": {"sha": "HEAD"},
            "labels": [],
        }
    }))

    # A line-anchored conformance_break finding on svc.py:2 (an added line → must survive).
    # Using conformance_break (not intent_unmet) because the new render_verdict shows
    # intent_unmet only in the criteria list; conformance_break appears in the breaks section
    # with its file anchor, letting us assert the line made it through the gate.
    # delivery_review now fans out via review_core.run_review, which binds these
    # reviewer names into its OWN module namespace at review_core's import time
    # (`from reconcile import review_edge_a`, etc.) — patching `reconcile`/
    # `behavioral_review` attributes directly no longer reaches the call sites
    # review_core actually uses (a stale attribute lookup would only work by
    # coincidence of import order). Patch review_core's own names instead.
    import review_core as core
    surviving = {
        "id": "f_cf_line", "kind": "conformance_break", "edge": "B",
        "problem_statement": "violates inv-auth",
        "anchor": {"file": "svc.py", "line": 2, "changed": True},
        "assumptions": ["invariant inv-auth"], "evidence": ["missing check"],
        "falsification": "wired elsewhere", "confidence": 0.9,
        "source": "reconcile:conformance", "severity_class": "tradeoff_undermined",
        "severity": "high",
    }
    monkeypatch.setattr(core, "review_edge_a", lambda *a, **k: [surviving])
    monkeypatch.setattr(core, "review_edge_c", lambda *a, **k: [])
    monkeypatch.setattr(core, "review_conformance", lambda *a, **k: [])
    monkeypatch.setattr(core, "behavioral_review_run", lambda *a, **k: [])
    import universal_specialists as us
    monkeypatch.setattr(us, "review_one", lambda *a, **k: [])
    monkeypatch.setattr(core, "review_invariants", lambda *a, **k: [])

    posted = {}
    def spy_post(owner, repo, number, body, token):
        posted["body"] = body
    import intent_review as ir
    monkeypatch.setattr(ir, "post_or_update_comment", spy_post)

    env = {"GITHUB_EVENT_PATH": str(event), "GITHUB_TOKEN": "t",
           "GITHUB_REPOSITORY": "o/r"}
    status = dr.run_pr_gate(str(root), env)
    assert status["reviewed"] is True
    # The line-anchored finding on the changed line 2 survived → rendered in the comment.
    assert "svc.py:2" in posted.get("body", ""), (
        f"line-anchored finding was suppressed; body: {posted.get('body')}"
    )


# J2 — comment-injection / crash hardening
def test_sanitize_strips_newlines():
    """A field with embedded newlines cannot open a second Markdown block /
    inject a fake verdict heading on its own line."""
    out = dr._sanitize("a\n\n## Delivery review\n**Built the intent?** ALL PASS")
    assert "\n" not in out
    assert "\r" not in out
    # No lone '## Delivery review' heading survives on its own line.
    assert not any(line.strip() == "## Delivery review" for line in out.split("\n"))


def test_sanitize_neutralizes_all_mentions():
    """@ anywhere (not just token-start) must be neutralized — no live mention."""
    out = dr._sanitize("(@everyone) .@here a@b")
    assert "@​" in out  # every @ carries the zero-width space
    # No live "@everyone"/"@here"/"a@b" mention remains.
    assert "@everyone" not in out
    assert "@here" not in out
    assert "a@b" not in out


def test_render_verdict_nonnumeric_line_no_crash():
    """A non-numeric anchor line ('NaN') must not raise — render returns a str."""
    # intent_unmet findings appear in the criteria list (when spec is given) or are skipped in breaks.
    # Use a conformance_break finding to test anchor rendering in the breaks section.
    md = dr.render_verdict(
        {"intent_completeness": "1/1", "breaks": 1, "conflicts": 0},
        [{"kind": "conformance_break", "problem_statement": "p", "anchor": {"file": "x.py", "line": "NaN"},
          "source": "reconcile:edgeA"}],
    )
    assert isinstance(md, str)
    assert "x.py:" in md


# Task 4 — assemble_pr_intent tests
def test_assemble_pr_intent_prefers_story_no_resolve(tmp_path):
    """When a task story with facts exists, assemble_pr_intent returns its facts as
    acceptance_criteria without calling the LLM resolver (criteria already present)."""
    import story_store as ss
    ss.write_story(tmp_path, "b", "s1", "2026-07-06T090000",
                   story="We refactor auth.",
                   facts=[{"id": "f1", "text": "From file",
                           "from": {"src": "plan", "quote": "From file"}}],
                   non_goals=[], version=1)
    called = {"resolve": 0}
    spec = dr.assemble_pr_intent(tmp_path, {"head_ref": "b", "title": "T", "body": "body"}, {},
                                 run=lambda *a, **k: called.__setitem__("resolve", called["resolve"] + 1) or "{}")
    assert [c["text"] for c in spec["acceptance_criteria"]] == ["From file"]
    assert called["resolve"] == 0                                  # criteria already present -> no LLM resolve


def test_assemble_pr_intent_body_only_resolves(tmp_path):
    # no committed file -> resolve() runs on the PR body to produce criteria
    payload = '{"acceptance_criteria":[{"id":"t","text":"From body"}]}'
    spec = dr.assemble_pr_intent(tmp_path, {"head_ref": "b", "title": "Add export", "body": "tenant scoped"}, {},
                                 run=lambda *a, **k: payload)
    assert [c["text"] for c in spec["acceptance_criteria"]] == ["From body"]


def test_assemble_pr_intent_all_empty(tmp_path):
    spec = dr.assemble_pr_intent(tmp_path, {"head_ref": "b", "title": "", "body": ""}, {}, run=lambda *a, **k: "{}")
    assert spec.get("acceptance_criteria") == []


def test_render_verdict_shows_criteria_provenance_and_correction(tmp_path):
    spec = {"source": "sync", "confidence": "medium", "confirmed": False,
            "acceptance_criteria": [{"id": "ac1", "text": "tenant scoped"}, {"id": "ac2", "text": "rate limited"}]}
    verdict = {"intent_completeness": "1/2", "breaks": 0, "conflicts": 0, "unknown": 0}
    confirmed = [{"kind": "intent_unmet", "criterion_id": "ac2", "problem_statement": "no limiter",
                  "anchor": {"file": "x.py", "line": 4}, "source": "reconcile:edgeA"}]
    md = dr.render_verdict(verdict, confirmed, spec)
    assert "tenant scoped" in md and "rate limited" in md      # criteria listed
    assert "medium" in md and "unconfirmed" in md.lower()      # provenance + trust label
    assert "archie imprint" in md                               # correction loop stated


def test_run_pr_gate_auto_imprints_when_no_story(tmp_path, monkeypatch):
    """run_pr_gate must call story_synthesize.imprint() when no current story exists but turns were captured."""
    import json as _json

    # Set up a minimal git repo so diff_basis doesn't crash.
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")
    base_sha = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()

    # Write intent events but NO story.
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    events_file = archie_dir / "intent-events.jsonl"
    events_file.write_text(_json.dumps({"kind": "user_turn", "text": "Add rate-limiting", "ts": "2024-01-01T00:00:00Z"}) + "\n")

    event = tmp_path / "event.json"
    event.write_text(_json.dumps({
        "pull_request": {
            "number": 99, "changed_files": 1, "user": {"login": "human"},
            "base": {"ref": "main", "sha": base_sha}, "head": {"sha": "HEAD"},
            "labels": [],
        }
    }))

    imprint_calls = {"n": 0}

    import story_synthesize as _ss
    def fake_imprint(root, branch, session_id, timestamp, run=None):
        imprint_calls["n"] += 1
        # Write a minimal story so assemble_pr_intent finds it.
        import story_store as ss
        ss.write_story(root, branch, session_id, timestamp,
                       story="Rate-limiting feature.",
                       facts=[{"id": "f1", "text": "rate limited",
                               "from": {"src": "plan", "quote": "Add rate-limiting"}}],
                       non_goals=[], version=1)
        return tmp_path / ".archie" / "stories" / "test"

    monkeypatch.setattr(_ss, "imprint", fake_imprint)

    import reconcile as rc
    monkeypatch.setattr(rc, "review_edge_a", lambda *a, **k: [])
    monkeypatch.setattr(rc, "review_edge_c", lambda *a, **k: [])
    monkeypatch.setattr(rc, "review_conformance", lambda *a, **k: [])
    import behavioral_review as br
    monkeypatch.setattr(br, "review", lambda *a, **k: [])

    posted = {}
    def spy_post(owner, repo, number, body, token):
        posted["body"] = body
    import intent_review as ir
    monkeypatch.setattr(ir, "post_or_update_comment", spy_post)

    env = {"GITHUB_EVENT_PATH": str(event), "GITHUB_TOKEN": "t",
           "GITHUB_REPOSITORY": "o/r"}
    status = dr.run_pr_gate(str(tmp_path), env)
    assert status["reviewed"] is True
    assert imprint_calls["n"] == 1, "imprint() must be called when no current story exists but turns were captured"


def test_render_verdict_surfaces_possible_issues_section():
    import delivery_review as dr
    verdict = {"intent_completeness": "1/1", "breaks": 1, "possible_issues": 1, "conflicts": 0}
    confirmed = [
        {"kind": "behavioral_break", "problem_statement": "confident bug", "confidence": 0.9,
         "anchor": {"file": "a.py", "line": 5}, "source": "behavioral"},
        {"kind": "behavioral_break", "problem_statement": "maybe null deref", "confidence": 0.3,
         "anchor": {"file": "b.py", "line": 9}, "source": "behavioral"},
    ]
    body = dr.render_verdict(verdict, confirmed, {"acceptance_criteria": [{"id": "ac1", "text": "x"}]})
    assert "Possible issues" in body
    assert "maybe null deref" in body        # low-conf → advisory section
    assert "confident bug" in body           # high-conf → breaks section
    # the advisory one must appear AFTER the "Broke anything?" line
    assert body.index("confident bug") < body.index("Possible issues") < body.index("maybe null deref")


def test_render_verdict_includes_story_and_provenance():
    import delivery_review as dr
    verdict = {"intent_completeness": "1/1", "breaks": 0, "possible_issues": 0, "conflicts": 0}
    spec = {"story": "We add a per-run cost preview.",
            "acceptance_criteria": [{"id": "f1", "text": "total from live steps",
                                     "from": {"src": "plan", "quote": "computed fresh from live steps"}}]}
    body = dr.render_verdict(verdict, [], spec)
    assert "We add a per-run cost preview." in body        # story shown
    assert "computed fresh from live steps" in body        # per-fact provenance shown


def test_render_verdict_discloses_diff_truncation():
    import delivery_review as dr
    verdict = {"intent_completeness": "1/1", "breaks": 0, "possible_issues": 0, "conflicts": 0}
    spec = {"acceptance_criteria": [{"id": "ac1", "text": "x"}], "diff_truncated": True}
    body = dr.render_verdict(verdict, [], spec)
    assert "truncated" in body.lower()
