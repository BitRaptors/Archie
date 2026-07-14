# Task Story — Faithful Intent Imprint — Design

- **Status:** Approved in brainstorm; ready for implementation planning.
- **Date:** 2026-07-06
- **Branch:** `feature/archie-delivery-review`
- **Supersedes:** the acceptance-criteria synthesis in `docs/archie-intent-capture-design.md`
  (`intent_synthesize.py` — the LLM that invents `acceptance_criteria` from captured turns).

---

## 1. One-sentence summary

Replace the "LLM invents acceptance criteria from scattered turns" intent step with a
**silent imprint** of the user's own materials (ticket ⊕ inputs ⊕ plan) into a **task
story** — a human-facing narrative from which Archie derives a small set of **checkable
facts, each traceable to its source** — stored as one branch- and timestamp-versioned
file, session-scoped for grading.

---

## 2. Problem (why the current criteria feel "random")

The current flow captures verbatim user turns, then a single LLM call
(`intent_synthesize.build_synthesis_prompt`) is instructed to *"write concrete checkable
acceptance_criteria."* On the cost-preview showcase this expanded one requirement paragraph
into 10 criteria and exhibited four defects the user named directly:

1. **No provenance.** Criterion shape is `{id, text}` — there is no link back to the turn
   that motivated it. A user cannot tell where `ac5` came from.
2. **Invention, then self-grading.** The LLM invented specifics not in the requirement
   (an exact endpoint path, a `billable_step_count` field, one-test-per-behavior), then
   edge-A graded the code against those inventions. `ac7` ("response includes a
   `billable_step_count` field") was never requested — yet the code was marked failing for
   lacking it.
3. **Unratified.** `confirmed: false`, but nothing surfaced the criteria to the user; an
   auto-expanded, unreviewed rubric graded the PR.
4. **Under-grounded + nondeterministic.** Thin input → the model fills gaps with plausible
   detail; re-running yields a different set of ~10.

The fix is not "better AC prompts" — it is a different artifact: **imprint the user's plan
faithfully as a story, derive facts from that story, and make every fact traceable.**

---

## 3. Approved model (the four decisions)

1. **Source — merged.** The imprint fuses the *ticket* (optional) ⊕ *inputs* ⊕ *converged
   plan*, taken **from the user's side** (their stated inputs and asks), not the coding
   agent's plan. This preserves the clean-room property: we imprint *what the user wanted*,
   independent of *how the agent built it*.
2. **Form — story for humans, facts for grading.** The primary artifact is a short
   narrative (the story). Archie derives a handful of checkable **facts** *from* the story;
   the review grades the facts; humans read the story.
3. **UX — fully silent, inspect on demand.** The imprint happens at the
   discussion→implementation transition with no interruption. `archie story` shows it on
   demand; the PR verdict is where most users first see it. (Consistent with "the developer
   mostly doesn't touch Archie.")
4. **Mechanism — summarize → derive → trace.** Two passes: (1) an LLM *compresses* the
   merged sources into a faithful story (summary, not invention); (2) a second pass extracts
   facts *from the story*, each carrying a `from:` pointer to the source it came from. A
   fact with no traceable source is dropped.

---

## 4. Data artifact — one versioned file

Story **and** intent live in a single file: readable prose (the story) + a fenced JSON
block (the graded layer). Parseable with the existing `evidence_schema.extract_json_obj`
(regex-extracts the JSON) — **no new dependency** (Archie stays stdlib-only).

**Path (versioned by branch + timestamp):**
```
.archie/stories/<branch-slug>/<timestamp>.md
```
- `<branch-slug>` — the branch with slashes flattened (`feature/run-cost-preview` →
  `feature-run-cost-preview`).
- `<timestamp>` — `YYYY-MM-DDThhmm` (same stamp format as `intent_capture._now`).

**File shape:**
```markdown
# Cost preview for a run

We add a per-run cost preview so the dashboard can show what a run cost. Given a
run_id, return the itemized billable steps and the total, computed fresh from the
live ledger. Step names count once. The 7-step cap is out of scope.

<!-- archie:facts -->
​```json
{
  "branch": "feature/run-cost-preview",
  "session_id": "<session id or session-start marker>",
  "imprinted_at": "2026-07-06T0912",
  "version": 2,
  "supersedes": "2026-07-06T0831",
  "source": "sync",
  "confirmed": false,
  "facts": [
    {"id": "f1", "text": "total = live billable steps × per-step price",
     "from": {"src": "plan", "quote": "the total must be the NUMBER of steps ×…"},
     "kind": "constraint"}
  ],
  "non_goals": ["applying the 7-step cap"]
}
​```
```

- **Prose = the story** (read raw, edit raw, or `archie story`).
- **Fenced JSON = the graded layer.** `facts[]` are the units edge-A grades; each has
  `text`, `from` (provenance: `src` ∈ {ticket, input, plan} + the `quote`/anchor it came
  from), and `kind` ∈ {goal, constraint, scope}. `non_goals` are threaded to the reviewers.

---

## 5. Versioning and session-scoped currency

Retention and currency are **separate concerns.**

- **Retention — keep everything.** Each imprint is its own timestamped file; history
  accrues so the evolution of a task's story is diffable in the branch. Nothing is pruned.
- **Currency — session-scoped.** The review grades against **the story imprinted during the
  current session**, not the accumulation of all versions on the branch. Each version is
  stamped with `session_id` (from the hook payload; falls back to a session-start marker
  file when a CLI does not provide one) alongside `branch` + `imprinted_at`.
- **Resolution at PR/CI time.** "Current" resolves to the **newest committed version for the
  branch** — in practice the latest imprint from the session that produced the PR.
  Older-session versions remain as history and never grade.
- **Re-plan within a session** → versions reconcile into the session-current story (facts
  added / kept / **retired** — killing the scope ratchet). Versions from *earlier* sessions
  are never merged in.

A task worked across three sessions has three story arcs on the branch; a PR is judged
against the arc from the session that built it, not a blur of all three.

---

## 6. Components

**6.1 `intent_capture.py` — unchanged.** Already silently logs the user's verbatim turns at
the transition (the "inputs + plan, user-side" source) into `.archie/intent-events.jsonl`.
Clean-room preserved; slash-commands and internal-spawn turns already filtered.

**6.2 Ticket (optional, thin).** If a ticket reference is present — a `TICKET:` line in a
captured turn, or a committed `.archie/ticket.md` — its text is included as a source with
`src: ticket`. **No Linear/Jira API in this spec** (YAGNI); a fetched ticket becomes an
additional high-confidence source later.

**6.3 `story_synthesize.py` (new; replaces `intent_synthesize.py`'s AC path).** Blind to
code. Two pure prompt-builders + parsers, LLM via `run_verifier`:
- `gather_sources(root) -> list[dict]` — reads the events log (+ optional ticket) into
  `[{src, text}]`.
- `build_story_prompt(sources) -> str` / `parse_story(raw) -> str` — Pass 1: faithful story.
- `build_facts_prompt(story, sources) -> list[dict]` / `parse_facts(raw)` — Pass 2: facts
  with `from` provenance.
- `imprint(root, run=None) -> Path` — orchestrates both passes, validates provenance,
  writes the versioned file (atomic), stamps branch/session/timestamp/version/supersedes.

**6.4 `archie story` command (new; `sync.py` subcommand).**
- `sync.py story <root>` — pretty-print the current story + facts + provenance.
- `sync.py story <root> --history` — list versions for the branch.
- `sync.py story <root> <timestamp>` — show a specific past version.

**6.5 Verdict render (evolve `delivery_review.render_verdict`).** The verdict gains the
story (collapsible) on top, then per-fact built/missed with each fact's `from:` source.

---

## 7. Data flow

```
planning:  user turns (inputs + asks) ──hook──▶ .archie/intent-events.jsonl      [silent]
           (+ optional .archie/ticket.md)
transition (plan→impl):  imprint (silent)
    sources = ticket ⊕ input/plan turns
    Pass 1  sources ──summarize──▶ story prose        (faithful; every sentence sourced)
    Pass 2  story   ──derive─────▶ facts[] {text, from}   (each fact cites its source)
    write   .archie/stories/<branch-slug>/<ts>.md   (prose + fenced facts; versioned)

PR (CI):   load newest session-current story for the branch
           facts ⊕ PR body  ──▶ edge-A grades facts ▸ behavioral/invariant edges unchanged
           verdict renders: story + per-fact ✓/✗ + provenance

anytime:   archie story [--history | <timestamp>]
```

---

## 8. Faithfulness guardrails (the anti-"random" core)

- **Pass 1 (story) instruction:** *"Summarize the sources below into a short task story.
  Every sentence MUST be supported by a source. Do NOT add endpoints, field names, tests, or
  requirements that are not present in the sources."*
- **Pass 2 (facts) instruction:** *"Extract only facts stated or directly implied by the
  story. Each fact MUST cite the source text it derives from. Do not invent specifics
  (paths, field names, test cases) not present."*
- **Provenance validation (mechanical):** any fact whose `from` is empty or whose `quote`
  does not match a source turn is **discarded** before it can grade. This is the hard
  guarantee against invention — the `billable_step_count` fact could not survive.
- **Provenance renders everywhere:** `archie story`, the file itself, and the PR verdict.

---

## 9. Grading integration

- edge-A already grades a list of `{id, text}`; point it at `facts` (same shape — a fact is
  a criterion with provenance). It flags unmet facts; "silence = met" semantics unchanged.
- `assemble_pr_intent` loads the session-current story's facts (replacing the old
  `intent.json` read) ⊕ PR body — same downstream shape as before.
- Behavioral and invariant (contract→tracer→challenger) edges are unchanged.
- The verdict header keeps `source` / `confidence` / confirmed-vs-unconfirmed labeling.

---

## 10. Degradation / edge cases

- **No sources captured** (pure-exploration branch) → no story written; the PR falls back to
  PR-body intent, labeled low-confidence (as today).
- **Bad LLM output** (either pass) → prior version left intact; no partial file (atomic
  `os.replace`). A story with zero surviving facts is still written (narrative-only) but
  grades nothing.
- **Malformed fenced JSON** on read → `extract_json_obj` yields `{}`; the loader falls back
  to PR-body intent.
- **Branch with no `stories/<slug>/`** → treated as "no story."
- **Hooks best-effort:** imprint failure never blocks the agent's action (exit 0).

---

## 11. Retired

Removed cleanly — nothing in the wild depends on the old shape, so **no compatibility
shim**:

- `intent_synthesize.py`'s acceptance-criteria invention and the un-provenanced
  `acceptance_criteria` shape.
- `.archie/intent.json` as the intent source of truth. `assemble_pr_intent` reads the
  versioned story file directly; the legacy `intent.json` read is deleted outright.

---

## 12. Out of scope (YAGNI)

- Linear/Jira ticket fetch (accept a pasted `TICKET:` / `.archie/ticket.md` only).
- A human-confirmation gate (the UX is silent; `confirmed` stays advisory metadata).
- Any back-and-forth / interview flow to elicit intent.
- History pruning / retention limits (keep everything).

---

## 13. Testing

- **story_synthesize:** `gather_sources` reads events (+ ticket); Pass-1/Pass-2 prompt
  builders are pure and asserted to contain the faithfulness instructions and the sources;
  parsers tolerate malformed output; **provenance validation drops un-sourced facts**
  (assert the `billable_step_count`-style invention is discarded); blindness contract
  (built prompts contain no code/diff).
- **Versioning:** path uses `<branch-slug>/<timestamp>`; a re-imprint writes a new version
  with `supersedes` set; slug flattens slashes.
- **Session currency:** given multiple versions across sessions, the resolver returns the
  newest of the *current* session; earlier-session versions excluded.
- **Single-file round-trip:** write → read back the fenced facts via `extract_json_obj`;
  prose preserved.
- **`archie story`:** renders current, `--history` lists versions, `<timestamp>` shows a
  past cut.
- **Verdict render:** includes the story + per-fact status + provenance.

---

## 14. Open follow-ups (not blocking)

- Ticket fetch (Linear) as an additional source.
- Optional lightweight ratification surface if silent proves too hands-off in practice.
- Multi-pass fact derivation to further reduce nondeterminism, if it persists after the
  faithfulness guardrails.
