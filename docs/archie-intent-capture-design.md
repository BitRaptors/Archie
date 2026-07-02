# Clean-Room Intent Capture — Design

- **Status:** Approved in brainstorm; ready for implementation planning.
- **Date:** 2026-07-02
- **Branch:** `feature/archie-delivery-review`
- **Supersedes:** the sync-SKILL "agent authors criteria silently" capture step in
  `docs/archie-branch-intent-design.md` §5.5.
- **Motivated by:** two adversarial reviews of the branch-intent feature — the *circularity*
  finding (the coding agent authors both the code and the criteria it's graded against → the
  headline "3/3 built" measures self-consistency, not correctness) and the *transparency* finding
  (the yardstick is captured silently, never shown, and reported as bare fractions).

---

## 1. One-sentence summary

Capture the user's intent at the **discussion→implementation transition** via a general, dependency-free
tool hook that cheaply logs the *verbatim* requirement, then have an **isolated agent that is blind to
the code** turn those logged events into acceptance criteria — producing a transparent, versioned,
human-ratifiable `.archie/intent.json` that the coding agent never authors and cannot silently edit.

---

## 2. Problem (from the reviews)

1. **Circularity / false green.** Today the coding agent — full of its own (possibly wrong)
   understanding — authors the acceptance criteria. edge-A then grades the diff against them. If the
   agent misread the task, criteria and code are wrong together and the verdict is a confident false
   green. The independence that matters is **source** (criteria from the *requirement*, not the
   *implementation*) and **blindness** (the criteria author never sees the code).
2. **Invisibility.** Capture is silent (`cmd_write_intent` prints one stderr line; the SKILL never
   shows the user the criteria). The PR verdict renders bare fractions with no criteria list, no
   provenance, no confidence, no correction path. The user is graded against a yardstick they never saw.
3. **No dependency on external skills.** Archie ships into arbitrary repos via `npx`; the capture
   trigger must be built from **agent-native primitives** (tool hooks), not gstack/superpowers/any
   library that may be absent.

---

## 3. Approach (approved)

**Two layers + transparency, all dependency-free.**

- **A) Cheap capture (deterministic hook, no LLM).** Ride the `PreToolUse` edit hook Archie *already*
  installs, plus a user-prompt hook. Detect the **discussion→implementation transition** (a run of
  conversation/reasoning turns followed by the first code-mutating action) and append the *verbatim*
  user/planning turns to an append-only, committed **intent-event log**. Fully general; fires
  repeatedly across a session, so intent is a **forward-looking, multi-point stream**.
- **B) Clean transform (isolated agent, blind to code).** A dedicated command dispatches an agent
  whose entire input is the raw intent-event log — *never* the diff, the code, or the coding
  conversation. It reconciles the events into `.archie/intent.json` acceptance criteria. Blindness is
  enforced by the command constructing a minimal prompt from the events file only.
- **C) Transparency (first-class, see §6).** Every capture is announced; the criteria are surfaced
  and human-ratifiable before they become the yardstick; provenance + confidence + capture history
  ride the spec and the PR verdict; the correction loop is explicit.

This breaks the circularity (criteria derive from the user's words, authored blind to the code), kills
the scope ratchet (versioned, deliberate events; scope can shrink), and makes the whole thing
auditable.

---

## 4. Data artifacts

**4.1 `.archie/intent-events.jsonl`** — append-only, committed. One raw event per line:
```json
{"ts":"2026-07-02T1412","kind":"user_turn","phase":"planning","text":"<verbatim user text>"}
{"ts":"2026-07-02T1440","kind":"transition","phase":"implementation","note":"first edit after 6 discussion turns","text":"<recent planning turns>"}
```
- `kind`: `user_turn` (a user message) or `transition` (discussion→implementation boundary).
- `text`: verbatim source text — the user's own words / the plan as discussed. **Never** a coding-agent
  paraphrase, **never** code.
- Deterministic, no LLM, cheap to append. Committed so it travels with the branch and is auditable.

**4.2 `.archie/intent.json`** — the reconciled current spec (same downstream shape as today, plus
transparency metadata):
```json
{
  "source": "sync",
  "confidence": "medium",
  "goals": ["..."],
  "acceptance_criteria": [{"id":"ac1","text":"...","from_events":["2026-07-02T1412"]}],
  "non_goals": ["..."],
  "ticket_id": "ARCH-123",
  "confirmed": false,
  "capture_points": 3,
  "captured_at": ["2026-07-02T1412","2026-07-02T1440","2026-07-02T1602"],
  "synthesized_at": "2026-07-02T1605",
  "updated": "2026-07-02T1605"
}
```
- `confirmed`: whether a human ratified the criteria (§6.2).
- `from_events` / `capture_points` / `captured_at`: provenance — which raw events each criterion came
  from, and how many planning moments fed this spec.

## 5. Components

**5.1 Capture hook — `intent_capture.py` (deterministic, no LLM)**
- `record_user_turn(root, text) -> None` — append a `user_turn` event (called from a user-prompt hook).
- `record_transition(root, recent_turns) -> None` — append a `transition` event (called from the
  `PreToolUse` edit hook when the first edit follows a planning stretch).
- `_hook_state(root)` — tiny state in `.archie/tmp/` tracking turns-since-last-edit so a transition
  fires once per discussion→implementation boundary, not on every edit.
- Wired into `install_hooks.py`: the existing `PreToolUse` edit hook (`pre-validate.sh`) gains a
  cheap call to `record_transition`; a user-prompt hook calls `record_user_turn`. Both are additive
  and must never block or fail the agent (any error → silent no-op, exit 0). For non-Claude CLIs the
  equivalent hook events are used via the existing `agent_cli` abstraction; where a CLI has no hook,
  capture degrades to the explicit command (§5.3) — no crash.

**5.2 Clean transform — `intent_synthesize.py` (isolated agent, blind to code)**
- `synthesize(root, run=None) -> dict` — reads ONLY `.archie/intent-events.jsonl`, dispatches an agent
  whose prompt contains *only* those events + the instruction *"You author acceptance criteria from
  this requirement. You are NOT shown the implementation. Do not assume how it was built."*, parses the
  result (reusing `evidence_schema.extract_json_obj`), and **reconciles** into `.archie/intent.json`.
- **Reconcile, not blind-union:** criteria may be added, kept, or **retired** relative to the prior
  spec (a re-plan can drop a criterion) — killing the ratchet. Retirements are recorded in history.
- Blindness is structural: the function never reads the diff, blueprint code, or sync conversation.

**5.3 Command surface (transparent + dependency-free) — `sync.py` subcommands**
- `sync.py capture-intent <root> [--text "..."]` — explicit capture (manual override / no-hook CLIs).
- `sync.py synthesize-intent <root>` — run the clean transform now; prints the resulting criteria.
- `sync.py show-intent <root>` — pretty-print the current `.archie/intent.json`: goals, criteria (with
  ids + provenance), source, confidence, capture points, confirmed?.
- `sync.py confirm-intent <root>` — set `confirmed: true` (human ratification; §6.2).

**5.4 Downstream — unchanged.** `assemble_pr_intent`, `merge_specs`, edge-A, behavioral, conformance
consume `.archie/intent.json` exactly as today. This design only changes *who authors it and how
visibly*. (`non_goals` is threaded through `merge_specs` + the reviewer prompts — the prior gap — so
scope-creep is actually checked.)

## 6. Transparency (the emphasized requirement)

**6.1 Every capture is announced.** The hook, on recording a transition, emits one short line the user
sees: `📝 Archie captured intent from your last planning turns — run 'archie show-intent' to review.`
No silent yardstick.

**6.2 Human ratification before it grades.** After `synthesize-intent`, the criteria are rendered for
the user to confirm or edit; `.archie/intent.json.confirmed` flips to `true` only on explicit
`confirm-intent` (or an edit). The PR verdict states whether the yardstick was human-confirmed vs
auto-synthesized-unconfirmed — so a `3/6` derived from ratified criteria and one from an unconfirmed
guess never look identical.

**6.3 Provenance & confidence are always visible.** `show-intent` and the PR verdict header render:
which sources fed the spec, the confidence, how many planning points captured it, and per-criterion
`from_events`.

**6.4 The verdict comment is self-explanatory** (folds in the transparency-redesign from the review):
renders the full criteria list with per-criterion ✅/❌, a provenance/confidence header, per-finding
reviewer + one-line reasoning, and a stated correction loop ("intent wrong? edit `.archie/intent.json`
and push — this updates"). Skips/degradations surface in the PR, never log-only.

**6.5 Full audit trail.** `intent-events.jsonl` (raw, verbatim) + `intent.json` history make the
evolution of intent inspectable in the branch diff: what was intended, when, and how it changed.

## 7. Data flow

```
session:  user brainstorms/plans ─(user-prompt hook)→ append user_turn events
          first edit after planning ─(PreToolUse edit hook)→ append transition event
                                     └→ "📝 intent captured — archie show-intent"
          (repeats at every re-plan → implementation boundary: multi-point stream)

synthesize (isolated, blind to code):
          .archie/intent-events.jsonl ──▶ clean agent (events ONLY) ──▶ reconcile ──▶ .archie/intent.json
          └→ criteria rendered for human confirm/edit  →  confirmed: true

PR:       assemble_pr_intent(committed intent.json ⊕ PR body) → edge-A + intent-aware code review
          → verdict comment: criteria list, per-criterion ✅/❌, provenance/confidence, correction loop
```

## 8. Error handling / degradation

- Hooks are best-effort: any failure → silent no-op, exit 0 (never block or fail the agent's action).
- No events captured (pure exploratory branch, or a CLI without hooks) → `synthesize` writes nothing;
  the PR falls back to PR-body intent, labeled low-confidence/post-hoc.
- Malformed events line → skipped. Transform-agent bad output → `extract_json_obj` yields `{}` → prior
  `intent.json` left intact.
- `intent.json` stays committed and non-gitignored; writes are atomic (`os.replace`).

## 9. Testing

- `intent_capture`: transition fires once per discussion→edit boundary (state machine); `record_*`
  append verbatim, no LLM, tolerate concurrent appends; hook failure → no-op exit 0.
- `intent_synthesize`: reads ONLY the events file (assert it never opens the diff/code); reconcile
  adds/keeps/**retires** criteria vs prior spec; bad agent output leaves prior spec intact; blindness
  contract (the dispatched prompt contains no code) asserted on the built prompt string.
- `sync` subcommands: `show-intent` renders goals/criteria/provenance/confirmed; `confirm-intent`
  flips the flag; `capture-intent --text` appends an event.
- `non_goals` threaded through `merge_specs` + present in the reviewer prompt.
- Transparency: verdict comment includes the criteria list, per-criterion status, provenance header,
  and correction-loop footer (render test).

## 10. Out of scope / follow-ups

- The heavier verdict-comment redesign (§6.4) may land as its own task if this spec grows too large —
  it is transparency-critical but mechanically separable from capture.
- Linear ticket fetch (still deferred; when present it becomes an additional, high-confidence event
  source feeding the same log).
- A smart per-turn "is this requirement-bearing?" classifier — start with capture-all + let the
  isolated transform filter (no per-event LLM cost).
