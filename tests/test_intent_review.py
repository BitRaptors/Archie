"""Tests for intent_review.py — the PR-time semantic review.

Covers the deterministic, network-free core: keyed diff, base-ref fetch, ledger glob,
event parsing, the conservative ledger join, the deterministic-field overwrite +
because-or-suppress filter, and comment rendering. The two network calls
(call_anthropic, post_or_update_comment) are exercised with monkeypatched urllib.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

import intent_review as ir  # noqa: E402


# ---------------------------------------------------------------------------
# git helpers (mirror test_sync.py)
# ---------------------------------------------------------------------------
def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "checkout", "-q", "-b", "main")
    return tmp_path


def _write(root: Path, rel: str, data) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) if not isinstance(data, str) else data)


def _commit(root: Path, msg: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", msg)


# ---------------------------------------------------------------------------
# normalize_rules
# ---------------------------------------------------------------------------
def test_normalize_rules_shapes():
    assert ir.normalize_rules({"rules": [{"id": "r1"}]}) == [{"id": "r1"}]
    assert ir.normalize_rules([{"id": "r1"}]) == [{"id": "r1"}]
    assert ir.normalize_rules(None) == []
    assert ir.normalize_rules({}) == []
    assert ir.normalize_rules({"rules": "bad"}) == []
    assert ir.normalize_rules(42) == []


# ---------------------------------------------------------------------------
# keyed_diff
# ---------------------------------------------------------------------------
def test_keyed_diff_remove_update_add():
    base = [{"id": "a", "v": 1}, {"id": "b", "v": 1}]
    branch = [{"id": "b", "v": 2}, {"id": "c", "v": 1}]
    diffs = {d["key"]: d for d in ir.keyed_diff(base, branch, "id", "v")}
    assert diffs["a"]["status"] == "REMOVE"
    assert diffs["b"]["status"] == "UPDATE"
    assert "v" in diffs["b"]["fields_changed"]
    assert diffs["c"]["status"] == "ADD"


def test_keyed_diff_reorder_is_noop():
    base = [{"id": "a", "v": 1}, {"id": "b", "v": 2}]
    branch = [{"id": "b", "v": 2}, {"id": "a", "v": 1}]
    assert ir.keyed_diff(base, branch, "id", "v") == []


def test_keyed_diff_title_hash_fallback():
    # no id field -> keyed on hash of the title field
    base = [{"title": "Tenant isolation", "body": "x"}]
    branch = [{"title": "Tenant isolation", "body": "y"}]
    diffs = ir.keyed_diff(base, branch, None, "title")
    assert len(diffs) == 1
    assert diffs[0]["status"] == "UPDATE"
    assert diffs[0]["key"] == ir._hash_title("Tenant isolation")


def test_keyed_diff_handles_missing_or_nonlist():
    assert ir.keyed_diff(None, None, "id", "t") == []
    add_only = ir.keyed_diff([], [{"id": "x"}], "id", "t")
    assert add_only[0]["status"] == "ADD"


# ---------------------------------------------------------------------------
# fetch_base_file / load_branch_file
# ---------------------------------------------------------------------------
def test_fetch_base_file_present_and_absent(tmp_path):
    root = _init_repo(tmp_path)
    _write(root, ".archie/blueprint.json", {"domain_invariants": [{"id": "d1"}]})
    _commit(root, "base")

    exists, data, err = ir.fetch_base_file(root, "main", ".archie/blueprint.json")
    assert exists and err is None
    assert data["domain_invariants"][0]["id"] == "d1"

    # absent file on the ref -> (False, None, None) => treat as all-ADD
    exists, data, err = ir.fetch_base_file(root, "main", ".archie/rules.json")
    assert exists is False and data is None and err is None


def test_fetch_base_file_malformed(tmp_path):
    root = _init_repo(tmp_path)
    _write(root, ".archie/blueprint.json", "{not valid json")
    _commit(root, "bad")
    exists, data, err = ir.fetch_base_file(root, "main", ".archie/blueprint.json")
    assert exists is True and data is None and err is not None


def test_load_branch_file_missing_and_empty(tmp_path):
    root = _init_repo(tmp_path)
    exists, data, err = ir.load_branch_file(root, ".archie/rules.json")
    assert exists is False and data is None
    _write(root, ".archie/rules.json", "")
    exists, data, err = ir.load_branch_file(root, ".archie/rules.json")
    assert exists is True and data == {} and err is None
    # empty rules normalize to []
    assert ir.normalize_rules(data) == []


# ---------------------------------------------------------------------------
# glob_ledger
# ---------------------------------------------------------------------------
def test_glob_ledger_unions_and_skips_malformed(tmp_path):
    root = _init_repo(tmp_path)
    # base commit with no changes dir
    _write(root, "seed.txt", "seed")
    _commit(root, "seed")

    _write(root, ".archie/changes/change_1.json",
           {"claims": [{"id": "rule:a", "kind": "rule", "statement": "A"}]})
    _write(root, ".archie/changes/change_2.json",
           {"claims": [{"id": "behavior:b", "kind": "behavior", "statement": "B"},
                       {"id": "rule:a", "kind": "rule", "statement": "A"}]})  # dup id
    (root / ".archie/changes/change_3.json").write_text("{bad json")
    (root / ".archie/changes/latest.json").write_text(
        json.dumps({"claims": [{"id": "z", "kind": "rule", "statement": "Z"}]}))

    claims = ir.glob_ledger(root, "main")
    ids = sorted(c["id"] for c in claims)
    # union of change_1 + change_2, dedup rule:a, malformed skipped, latest.json ignored
    assert ids == ["behavior:b", "rule:a"]


def test_glob_ledger_excludes_records_on_base(tmp_path):
    root = _init_repo(tmp_path)
    _write(root, ".archie/changes/change_1.json",
           {"claims": [{"id": "old", "kind": "rule", "statement": "old"}]})
    _commit(root, "base has change_1")
    _git(root, "checkout", "-q", "-b", "feature")
    _write(root, ".archie/changes/change_2.json",
           {"claims": [{"id": "new", "kind": "rule", "statement": "new"}]})
    _commit(root, "feature adds change_2")

    claims = ir.glob_ledger(root, "main")  # base = main (only has change_1)
    ids = [c["id"] for c in claims]
    assert ids == ["new"]  # change_1 is on base -> excluded


# ---------------------------------------------------------------------------
# parse_event_context
# ---------------------------------------------------------------------------
def test_parse_event_context_ok(tmp_path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 42, "base": {"ref": "main"}}}))
    ctx = ir.parse_event_context({
        "GITHUB_REPOSITORY": "octo/repo",
        "GITHUB_BASE_REF": "main",
        "GITHUB_EVENT_PATH": str(event),
    })
    assert ctx == ("octo", "repo", 42, "main")


def test_parse_event_context_pulls_base_from_payload(tmp_path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 7, "base": {"ref": "develop"}}}))
    ctx = ir.parse_event_context({
        "GITHUB_REPOSITORY": "octo/repo",
        "GITHUB_BASE_REF": "",
        "GITHUB_EVENT_PATH": str(event),
    })
    assert ctx == ("octo", "repo", 7, "develop")


def test_parse_event_context_rejects_non_pr(tmp_path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"push": {}}))
    ctx = ir.parse_event_context({
        "GITHUB_REPOSITORY": "octo/repo",
        "GITHUB_BASE_REF": "main",
        "GITHUB_EVENT_PATH": str(event),
    })
    assert ctx is None
    # malformed repo
    assert ir.parse_event_context({"GITHUB_REPOSITORY": "noslash"}) is None


# ---------------------------------------------------------------------------
# build_changed_items
# ---------------------------------------------------------------------------
def test_build_changed_items_invariant_remove_and_claim():
    base_bp = {"domain_invariants": [
        {"id": "INV1", "invariant": "tenant writes scoped", "keywords": ["tenant"],
         "enforced_at": ["db/payments.py:10"]}]}
    branch_bp = {"domain_invariants": []}  # removed
    claims = [{"kind": "behavior", "statement": "DunningJob calls stripe directly",
               "evidence_files": ["jobs/dunning.py"]}]
    items = ir.build_changed_items(base_bp, branch_bp, [], [], claims)
    inv = [i for i in items if i["section"] == "domain_invariants"]
    assert inv and inv[0]["diff_op"] == "REMOVE" and inv[0]["layer"] == 1
    assert inv[0]["enforced_at_files"] == ["db/payments.py"]
    desc = [i for i in items if i["source"] == "ledger"]
    assert desc and desc[0]["layer"] == 2 and desc[0]["diff_op"] == "DECLARED"
    # every item has a unique ref
    refs = [i["ref"] for i in items]
    assert len(refs) == len(set(refs))


def test_build_changed_items_rule_remove_and_add():
    base_rules = [{"id": "R1", "description": "no direct stripe"}]
    branch_rules = [{"id": "R2", "description": "cap retries at 3"}]
    items = ir.build_changed_items({}, {}, base_rules, branch_rules, [])
    ops = {i["title"]: i["diff_op"] for i in items if i["source"] == "rules"}
    assert ops["R1"] == "REMOVE"
    assert ops["R2"] == "ADD"


# ---------------------------------------------------------------------------
# ledger_join
# ---------------------------------------------------------------------------
def test_ledger_join_matches_on_file_and_keyword():
    item = {"enforced_at_files": ["db/payments.py"], "keywords": ["tenant", "writes"]}
    claims = [{"statement": "tenant writes now unscoped", "evidence_files": ["db/payments.py"],
               "confidence": "low", "reconstructed": True}]
    join = ir.ledger_join(item, claims)
    assert join and join["confidence"] == "low" and join["reconstructed"] is True


def test_ledger_join_no_match_returns_none():
    item = {"enforced_at_files": ["db/payments.py"], "keywords": ["tenant"]}
    # file matches but no keyword overlap
    assert ir.ledger_join(item, [{"statement": "unrelated change",
                                  "evidence_files": ["db/payments.py"],
                                  "confidence": "high"}]) is None
    # keyword matches but no file overlap
    assert ir.ledger_join(item, [{"statement": "tenant logic",
                                  "evidence_files": ["other/file.py"],
                                  "confidence": "high"}]) is None


# ---------------------------------------------------------------------------
# finalize_findings
# ---------------------------------------------------------------------------
def _items():
    return [
        {"ref": "c0", "diff_op": "REMOVE", "layer": 1, "section": "domain_invariants",
         "title": "Tenant isolation", "enforced_at_files": ["db/p.py"], "keywords": ["tenant"]},
        {"ref": "c1", "diff_op": "ADD", "layer": 1, "section": "rules",
         "title": "R2", "enforced_at_files": [], "keywords": ["retry"]},
    ]


def test_finalize_overwrites_and_suppresses():
    model = [
        # valid finding, but model lies about diff_op -> script overwrites
        {"item_ref": "c0", "type": "silent_weakening", "rule_name": "wrong",
         "what_changed": "removed", "because": "rule text says X", "diff_op": "ADD"},
        # because blank -> dropped
        {"item_ref": "c1", "type": "contradiction", "rule_name": "R2",
         "what_changed": "", "because": "   "},
        # ref doesn't exist -> dropped
        {"item_ref": "zzz", "type": "contradiction", "rule_name": "ghost",
         "what_changed": "x", "because": "y"},
    ]
    out = ir.finalize_findings(model, _items(), [])
    assert len(out) == 1
    f = out[0]
    assert f["diff_op"] == "REMOVE"          # overwritten from the item, not the model's "ADD"
    assert f["rule_name"] == "Tenant isolation"  # script-owned title, not model's "wrong"
    assert f["layer"] == 1
    assert f["because"] == "rule text says X"


def test_finalize_attaches_ledger_confidence():
    items = _items()
    claims = [{"statement": "tenant scoping dropped", "evidence_files": ["db/p.py"],
               "confidence": "low", "reconstructed": True}]
    model = [{"item_ref": "c0", "type": "silent_weakening", "rule_name": "x",
              "what_changed": "removed", "because": "cited"}]
    out = ir.finalize_findings(model, items, claims)
    assert out[0]["confidence"] == "low" and out[0]["reconstructed"] is True


# ---------------------------------------------------------------------------
# render_comment
# ---------------------------------------------------------------------------
def test_render_comment_no_diff_returns_none():
    assert ir.render_comment([], had_diff=False) is None


def test_render_comment_no_findings_is_consistent_message():
    body = ir.render_comment([], had_diff=True)
    assert ir.COMMENT_MARKER in body
    assert "consistent" in body.lower()


def test_render_comment_groups_and_cites():
    findings = [
        {"type": "silent_weakening", "diff_op": "REMOVE", "layer": 1,
         "rule_name": "Tenant isolation", "what_changed": "removed scoping",
         "because": "invariant text required tenant_id", "confidence": "low",
         "reconstructed": True},
        {"type": "behavior_violates_rule", "diff_op": "DECLARED", "layer": 2,
         "rule_name": "Centralized payments", "what_changed": "calls stripe directly",
         "because": "R2 forbids direct stripe", "confidence": None},
    ]
    body = ir.render_comment(findings, had_diff=True)
    assert ir.COMMENT_MARKER in body
    assert "Silent weakening" in body and "Behavior may violate" in body
    assert "Because:" in body
    assert "ledger confidence: low" in body
    assert "reconstructed guess" in body
    assert "doesn't block" in body


# ---------------------------------------------------------------------------
# model + github calls (monkeypatched urllib)
# ---------------------------------------------------------------------------
def test_extract_findings_from_tool_use():
    resp = {"content": [
        {"type": "text", "text": "ignore"},
        {"type": "tool_use", "name": "emit_findings",
         "input": {"findings": [{"item_ref": "c0", "type": "contradiction"}]}},
    ]}
    out = ir._extract_findings(resp)
    assert out == [{"item_ref": "c0", "type": "contradiction"}]
    assert ir._extract_findings({"content": []}) == []


def test_call_anthropic_parses_tool_use(monkeypatch):
    class FakeResp:
        def __init__(self, payload):
            self._b = json.dumps(payload).encode()
        def read(self):
            return self._b
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.headers.items()}
        return FakeResp({"content": [
            {"type": "tool_use", "name": "emit_findings",
             "input": {"findings": [{"item_ref": "c0", "type": "silent_weakening",
                                     "rule_name": "x", "what_changed": "y", "because": "z"}]}}]})

    monkeypatch.setattr(ir.urllib.request, "urlopen", fake_urlopen)
    out = ir.call_anthropic("sys", "user", "sk-test")
    assert out[0]["item_ref"] == "c0"
    assert captured["url"] == ir.ANTHROPIC_URL
    assert captured["headers"]["x-api-key"] == "sk-test"
    assert captured["headers"]["anthropic-version"] == ir.ANTHROPIC_VERSION


def test_post_or_update_comment_creates_then_updates(monkeypatch):
    calls = []

    def fake_gh(method, url, token, body=None):
        calls.append((method, url, body))
        if method == "GET":
            # first call: no existing comment; second call: existing with marker
            if len([c for c in calls if c[0] == "POST"]) == 0:
                return []
            return [{"id": 99, "body": ir.COMMENT_MARKER + "\nold"}]
        return {}

    monkeypatch.setattr(ir, "_gh_request", fake_gh)

    ir.post_or_update_comment("o", "r", 1, ir.COMMENT_MARKER + "\nnew", "tok")
    assert calls[-1][0] == "POST"  # created

    ir.post_or_update_comment("o", "r", 1, ir.COMMENT_MARKER + "\nnewer", "tok")
    assert calls[-1][0] == "PATCH"  # updated existing id 99
    assert "/comments/99" in calls[-1][1]
