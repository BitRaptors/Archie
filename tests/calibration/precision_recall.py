#!/usr/bin/env python3
"""Rule calibration harness — the "smoke alarm test".

For each rule, run it against KNOWN cases and see if it behaves:
  - positive cases  (code that really violates)                 -> should FIRE
  - negative cases  (clean code, incl. near-misses like the      -> should STAY QUIET
                     pattern sitting in a comment or string)

Count true/false positives -> precision & recall. A rule is `block_eligible`
(allowed to FAIL a build) only if its precision clears the bar; jumpy rules
degrade to WARN. The labels come from how each case was BUILT, never from the
rule's own output, so the measurement is non-circular. Reuses check_rules.py —
the exact engine the gate uses.

Run: python3 tests/calibration/precision_recall.py        # demo on a sample rule
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parents[2] / "archie" / "standalone"
CHECK_RULES = _STANDALONE / "check_rules.py"

# A rule must be at least this precise to be allowed to BLOCK a build. A wrong
# block costs more trust than ten good warns earn, so the bar is conservative.
PRECISION_BAR = 0.95


def evaluate(cases, fired) -> dict:
    """Pure scoring. cases: [{'id','label'}]; fired: ids the rule flagged."""
    fired = set(fired)
    pos = [c for c in cases if c["label"] == "positive"]
    neg = [c for c in cases if c["label"] == "negative"]
    tp = sum(1 for c in pos if c["id"] in fired)
    fn = sum(1 for c in pos if c["id"] not in fired)
    fp = sum(1 for c in neg if c["id"] in fired)
    tn = sum(1 for c in neg if c["id"] not in fired)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        # Only allow blocking when the rule actually caught at least one real
        # violation AND it was precise enough. No evidence -> never block.
        "block_eligible": (tp + fn) > 0 and precision >= PRECISION_BAR,
    }


def _run_check_rules(repo: Path) -> dict:
    proc = subprocess.run([sys.executable, str(CHECK_RULES), str(repo)],
                          capture_output=True, text=True, timeout=120)
    out = proc.stdout
    return json.loads(out[out.index("{"):])


def calibrate(rule: dict, cases: list) -> dict:
    """Build a throwaway repo with just this rule + the case files, run the real
    check_rules, and return the rule's precision/recall + block verdict."""
    tmp = Path(tempfile.mkdtemp(prefix="archie-cal-"))
    try:
        (tmp / ".archie").mkdir(parents=True, exist_ok=True)
        (tmp / ".archie" / "rules.json").write_text(json.dumps([rule]))
        for c in cases:
            p = tmp / c["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(c["content"])
        cr = _run_check_rules(tmp)
        fired_files = {v["file"] for v in cr.get("violations", [])
                       if v.get("rule_id") == rule.get("id")}
        fired_ids = {c["id"] for c in cases if c["path"] in fired_files}
        return evaluate(cases, fired_ids)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def write_calibration(repo, results: dict):
    """Persist .archie/rule_calibration.json = {rule_id: metrics} so the gate can
    read which rules are precise enough to block."""
    archie = Path(repo) / ".archie"
    archie.mkdir(parents=True, exist_ok=True)
    path = archie / "rule_calibration.json"
    path.write_text(json.dumps(results, indent=2) + "\n")
    return path


def demo():
    """A plausible 'no raw SQL in handlers' rule whose regex is too greedy: it
    matches the forbidden call even inside comments and strings."""
    rule = {
        "id": "no-raw-sql-in-handlers", "check": "forbidden_content",
        "severity_class": "decision_violation", "applies_to": "src/handlers",
        "forbidden_patterns": ["\\.execute\\(\\s*[\"'`].*(SELECT|INSERT|UPDATE|DELETE)"],
        "description": "Handlers must use the repository layer, not raw SQL.",
    }
    cases = [
        {"id": "violation", "label": "positive", "path": "src/handlers/order.py",
         "content": 'def get(c, i):\n    return c.execute("SELECT * FROM orders WHERE id=?", [i])\n'},
        {"id": "clean", "label": "negative", "path": "src/handlers/user.py",
         "content": 'def get(repo, i):\n    return repo.get(i)\n'},
        {"id": "comment_distractor", "label": "negative", "path": "src/handlers/legacy.py",
         "content": 'def get(repo, i):\n    # we no longer call c.execute("SELECT ...") here\n    return repo.get(i)\n'},
        {"id": "string_distractor", "label": "negative", "path": "src/handlers/msg.py",
         "content": 'ERR = "do not call c.execute(\\"SELECT\\") directly"\n'},
    ]
    return rule, cases, calibrate(rule, cases)


def main() -> int:
    rule, cases, m = demo()
    npos = sum(1 for c in cases if c["label"] == "positive")
    nneg = len(cases) - npos
    print(f"Calibrating rule:  {rule['id']}")
    print(f"  cases:     {len(cases)}  ({npos} should-fire, {nneg} should-stay-quiet)")
    print(f"  caught real violations:  {m['tp']}/{m['tp'] + m['fn']}  (recall {m['recall']})")
    print(f"  false alarms on clean code:  {m['fp']}  (precision {m['precision']})")
    if m["block_eligible"]:
        print(f"  verdict:  BLOCK-ELIGIBLE ✓  (precise enough — may fail a build)")
    else:
        print(f"  verdict:  WARN-ONLY ✗  (precision {m['precision']} < {PRECISION_BAR} "
              f"— too jumpy to block; tighten the regex to exclude comments/strings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
