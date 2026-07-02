# Branch Intent Capture — Design

- **Status:** Approved in brainstorm; ready for implementation planning.
- **Date:** 2026-07-02
- **Branch:** `feature/archie-delivery-review`
- **Fixes:** the dead `.archie/intent/<branch>.json` record loop (nothing writes it), so the
  delivery review's intent leg only ever sees the PR description. See
  `docs/archie-delivery-review-design.md` §5.

---

## 1. One-sentence summary

`/archie-sync` writes a **committed** `.archie/intent.json` on the branch (agent-authored goals +
acceptance criteria from the plan/conversation); the delivery review reads it at PR time and
**merges** it with an **optional** Linear ticket and the PR body, so the review grades against what
you actually set out to build — not just the PR write-up.

---

## 2. Problem

Traced in-session: the only writer of a branch intent record (`sync_review.py:88`) sits behind a
condition that can never fire on a first run (`raw` is always `""` because nothing seeds it), so
`.archie/intent/<branch>.json` is never created. `load_branch_record` therefore always returns
`None`, and `run_pr_gate` falls back to PR title/body only. Result: a thin PR body →
"Built the intent? 0/0", and the ticket/plan that defined the task is invisible.

## 3. Approach (approved)

- **Capture at write time, into a committed file.** `/archie-sync` (agent-driven) authors
  `.archie/intent.json` directly — goals + acceptance criteria — from the task/plan/conversation.
  It's committed with the branch (Archie repo-mode already commits non-ignored `.archie/*.json`),
  so it reaches CI in the PR checkout. No LLM `resolve()` needed for this source (the agent is the LLM).
- **Fetch the ticket at read time, optionally.** At PR time, if a `ticket_id` and `LINEAR_API_KEY`
  exist, fetch the Linear issue text and `resolve()` it into criteria. Best-effort — never a blocker.
- **Merge, not either/or.** Intent = union of criteria from committed file + ticket + PR body, with
  precedence only for the confidence label. All sources optional; all empty → `0/0` (honest).

Alternatives rejected: PR-body-only (the gap being closed); reviving the hashed per-branch record
(not a clean committed artifact; the user wants "commit it in").

---

## 4. The intent artifact — `.archie/intent.json`

Fixed committed path (branch-specific by virtue of living on the branch). Reuses the `intent_spec`
shape so the existing pipeline consumes it unchanged:
```json
{
  "source": "sync",
  "raw": "<goal + plan, free text>",
  "goals": ["Add tenant-scoped export", "Rate-limit to 10/min"],
  "acceptance_criteria": [
    {"id": "ac1", "text": "Export returns only the caller's tenant rows"},
    {"id": "ac2", "text": "Endpoint rate-limited to 10 req/min per tenant"}
  ],
  "ticket_id": "ARCH-123",
  "confidence": "high",
  "updated": "2026-07-02T1200"
}
```
- `acceptance_criteria` authored directly by the sync agent (no PR-time resolve for this source).
- `ticket_id` optional; used at PR time to attempt a Linear fetch.
- Idempotent: re-running sync **merges** (union criteria, keep populated fields; never clobber a
  populated list with an empty one).

## 5. Components

**5.1 `intent.py` additions**
- `INTENT_FILE = "intent.json"` (under `.archie/`).
- `load_committed_intent(root: Path) -> dict | None` — read `.archie/intent.json`, validate it's a
  dict, return the spec or `None`.
- `write_committed_intent(root: Path, spec: dict) -> None` — merge over any existing file
  (union `acceptance_criteria` by normalized text, union `goals`/`ticket_ids`, keep highest-rank
  `source`/`confidence`, refresh `updated`), then write atomically.
- `merge_specs(*specs: dict) -> dict` — pure union used by both the writer and the PR-time assembler.

**5.2 `linear_intent.py` (new, isolated, optional)**
- `fetch_ticket(ticket_id: str | None, api_key: str | None, post=<injected http>) -> str | None`
  — one Linear GraphQL query for the issue's title + description; returns text or `None` on missing
  input / any error. Network call is injected so tests never hit the network. Zero deps (stdlib
  `urllib`). Nothing else imports Linear.

**5.3 `delivery_review.run_pr_gate` — intent assembly (replaces the PR-body-only block)**
```
spec_file   = load_committed_intent(root)                 # committed on branch
ticket_id   = (spec_file or {}).get("ticket_id") or first ticket id in branch/PR text
ticket_text = fetch_ticket(ticket_id, env.get("LINEAR_API_KEY"))   # optional, may be None
spec_ticket = resolve(normalize(ticket_text, "linear", [ticket_id])) if ticket_text else None
spec_pr     = normalize(pr_title + "\n\n" + pr_body, "pr_body", tickets)
spec        = merge_specs(*filter(None, [spec_ticket, spec_file, spec_pr]))
if not spec.get("acceptance_criteria") and spec.get("raw"):
    spec = resolve(spec)      # only if nothing supplied criteria
```

**5.4 `sync_review.run_sync_review`**
- Read `load_committed_intent(root)` first (so `sync.py review` benefits too); fall back to the
  current `normalize("")` path. Remove reliance on the dead hashed record.

**5.5 `/archie-sync` command + `sync` workflow SKILL**
- Add an **intent-capture step**: the agent synthesizes goals + acceptance criteria for the branch
  from the task/plan and calls a small helper to write `.archie/intent.json`
  (e.g. `python3 .archie/sync.py write-intent <root> <json-file>` or the agent writes the file and
  stages it). The file is committed with the sync fold.
- Expose a `sync.py write-intent` subcommand that validates + merges + writes the spec (so the
  agent hands structured JSON to a deterministic writer rather than hand-editing).

**5.6 Workflow / setup**
- Add `LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}` to the delivery-review step in the canonical
  `archie-intent-review.yml`. Optional — absent key just skips the fetch.
- `setup-archie-intent-review.sh` optionally prompts for `LINEAR_API_KEY` (skippable).

## 6. Data flow

```
during work:  /archie-sync → agent authors goals+criteria → sync.py write-intent
                          → .archie/intent.json (merged, committed with the fold)

open PR:      run_pr_gate:
                load_committed_intent(checkout)           ─┐
                fetch_ticket(ticket_id, LINEAR_API_KEY)?  ─┼─ merge_specs → spec
                PR title/body                             ─┘
                → (resolve only if no criteria)
                → edge-A / behavioral / conformance → verdict comment
```

## 7. Error handling

Every source independently optional and guarded. No file → ticket/PR. No ticket id / no key /
Linear error → warn + skip. Malformed `.archie/intent.json` → treat as absent (warn). All empty →
`0/0`. `run_pr_gate` stays non-blocking, always exits 0. `write-intent` never crashes sync: on a bad
payload it logs and leaves any existing file untouched.

## 8. Testing

- `intent`: `load_committed_intent` (present / absent / malformed); `merge_specs` (union criteria,
  no clobber of populated by empty, precedence label); `write_committed_intent` (merge on re-write,
  atomic).
- `linear_intent`: `fetch_ticket` with injected fake post → returns text; missing id/key → `None`;
  HTTP error → `None` (no raise).
- `delivery_review`: PR gate merges file + ticket + PR body (mock fetch + mock LLM) → criteria from
  all sources present; file-only path (no ticket) → uses committed criteria without a resolve call;
  all-empty → `0/0`; Linear failure → still produces a verdict.
- `sync`: `write-intent` subcommand writes/merges `.archie/intent.json`; bad payload leaves file
  intact; smoke that the file round-trips into `run_sync_review`.

## 9. Out of scope / follow-ups

- Auto-detecting the ticket id from Linear's PR-link API (we read it from the intent file / branch /
  PR text for now).
- Jira/GitHub-Issues fetchers (the `fetch_ticket` seam generalizes later).
- The full `contract→tracer→challenger` specialist loop (separate).
