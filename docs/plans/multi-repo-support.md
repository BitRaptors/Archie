# Plan: Multi-repo support for Archie

**Status:** draft — design only, no implementation yet
**Date:** 2026-05-08
**Branch:** `feature/multi-repo`

---

## Problem

Customers running microservice fleets (50–80 repos) cannot use Archie effectively today. The single-repo blueprint describes each service in isolation but says nothing about cross-repo concerns — service-to-service contracts, shared SDKs, fleet-wide architectural drift. For these customers, a pile of 80 single-repo blueprints is not the same product as a fleet-aware view, even if all 80 are generated.

The blocker is twofold:

1. **Execution.** `/archie-deep-scan` is tied to a single Claude Code instance running in a single checked-out repo (`cwd`). Driving 50+ scans manually across separate sessions is impractical, and a single CC session blows context limits long before the work is done.
2. **Output.** Even with all module blueprints generated, there is no system-level synthesis — the architectural artifact a customer would actually look at to understand their fleet.

This work addresses both: an automation layer that drives per-module scans across many repos and survives rate-limit windows, plus a synthesis step that produces a system-level overview from whatever blueprints exist.

## Demand evidence

Two named buyers (anonymized in this doc) have independently raised multi-repo support as a blocker:

- **Buyer A** — connected via warm intro. Ran Archie on at least one of their own repos. Stated explicitly: until multi-repo works, they cannot properly use the product. Tolerates a slow / pricy v0 because seeing the multi-repo situation is what tells them whether to invest further. Named expectations: a C4-model architecture diagram + a memory describing the system and its components' rules. Test threshold: 50–60 repos ("basically the system").
- **Buyer B** — same shape of ask in a separate conversation. Less detail captured.

Both buyers' status quo is best read as "code-level intuition" — no service catalog, no full APM coverage, no living architecture diagram. The competitor for v0 is **the thing they don't have**.

## Out of v0 scope (explicitly deferred)

Several adjacent product surfaces came up in design but are deliberately **not** part of this work:

- **Per-PR cadence in CI.** Buyer A's eventual goal is an agent in CI that uses fleet context to review PR diffs. This requires diff-aware fast updates and is its own problem; out of scope here.
- **Anthropic API-key mode.** Driving fleet runs via a direct API key (rather than CC subscription) is a different product — different distribution, different billing, different customer journey.
- **GitHub-hosted CI runners.** Without API mode, GH-hosted runners cannot authenticate. "CI" in this work means self-hosted runners, customer-owned VMs, or containers — any persistent compute with `claude` installed and logged in.
- **Cross-repo enforcement.** v0 produces an analyst-time artifact. It does not block PRs, generate review verdicts, or run hooks across modules.
- **Refresh / re-fetch / branch pinning.** v0 clones the default branch once. Refresh is manual (delete folder, re-run prepare).
- **Auto-detection of team / domain ownership.** v0 has no notion of teams. If a customer's reality is heavily federated, that's a v0.5 metadata layer.

## Premises (working frame)

1. The unit of value is the **report**, not a continuous platform. v0 produces a periodic diagnostic artifact.
2. Cross-repo **dependencies** (the picture) are the v0 headline, not cross-repo enforcement (the verdict).
3. Slow + pricy v0 is allowed. Buyer said so explicitly.
4. **Per-repo Archie is the building block.** Fleet runs the existing `/archie-deep-scan` on each module; we add only a system-level overlay.
5. **Source code, not runtime.** No OTel / APM input. Cross-repo signal derived from code.
6. **Distribution is the existing CC + npx path.** No new install model, no hosted SaaS, no separate API surface.

## Approach: the system-folder model

The natural unit is a **system folder** containing modules as subdirectories — either symlinked to existing checkouts or freshly cloned from URLs. Conceptually: the system folder is "a big repo where each immediate child is a microservice module," and Archie's existing hierarchical analysis pattern applies one level higher.

```
acme-system/
├── repos.txt                    ← what to include
├── billing-service/             ← symlink to existing checkout
├── auth-service/                ← cloned from git URL
├── notification-service/        ← cloned from git URL
├── ...
└── .archie/
    ├── repos.lock.json          ← prep result, status registry
    ├── overview-blueprint.json  ← system-level synthesis
    ├── overview-c4.md           ← Mermaid C4 (Context + Container)
    ├── overview-scan-report.md  ← "see the situation" artifact
    ├── AGENTS.md                ← system-level memory
    ├── SCANS_COMPLETE           ← phase-1 marker
    └── FLEET_COMPLETE           ← phase-2 marker
```

Each module folder accumulates its own `.archie/blueprint.json` from a per-module deep-scan, identical to running `/archie-deep-scan` on the repo standalone.

## Three phases

The work splits into three independently restartable phases. **Failures only ever exclude — they never block.**

### Phase 1 — Prepare (one-shot, no AI)

`python3 archie/standalone/fleet.py prepare`

Reads `repos.txt`. For each entry:

| Entry type | Action | Status on success |
|---|---|---|
| Path that exists locally (`./relative` or `/abs`) | Symlink `<system>/<slug>` → resolved absolute path | `READY` |
| Path that doesn't exist | None | `UNAVAILABLE: path not found` |
| Git URL (`git@`, `https://`, `ssh://`, `*.git`) | Clone to `<system>/<slug>.tmp/`, atomic rename to `<system>/<slug>/` on success | `READY` |
| Git URL, folder already exists with `.git/` | None | `READY` |
| Git URL, folder exists without `.git/` | None | error (refuse to overwrite) |

Auth is the host machine's responsibility (SSH agent, `~/.gitconfig` credential helper, `gh auth`). v0 does not manage credentials; clone failures are surfaced as `UNAVAILABLE: <reason>`.

Output artifact: `.archie/repos.lock.json` — the per-module status registry that subsequent phases read.

### Phase 2 — Scan (long-running, wrapper-driven)

Slash command: `/archie-fleet-scan`

Reads `repos.lock.json`. For each `READY` module without `<module>/.archie/blueprint.json`:

1. Dispatch a Task subagent with the per-module dispatch prompt.
2. Subagent `cd`s into the module path and follows `~/.claude/commands/archie-deep-scan.md` exactly. **No copy of scan logic** — the per-module work IS the existing deep-scan, scoped to a different `cwd`.
3. Subagent overrides `$PROJECT_NAME=<slug>` so concurrent modules with identical repo basenames don't collide in `/tmp/archie_sub*_*.json`.
4. Returns `MODULE_DONE: <slug>` or `MODULE_FAILED: <slug> reason=...`

Best-effort, per-batch. Failed modules are noted, not retried in the same iteration. Default parallelism `K=3`; tunable via flag if a customer's plan tier supports more.

Designed to be invoked repeatedly by the wrapper. Each invocation makes monotonic progress (skips modules with existing blueprints) and exits cleanly when its iteration budget is spent or rate limits hit.

Marker: when no module is in `PENDING` state (every `READY` module either has a blueprint or is marked scan-failed), touch `.archie/SCANS_COMPLETE`.

### Phase 3 — Overview (fast, interactive-friendly)

Slash command: `/archie-fleet-overview`

Reads `<module>/.archie/blueprint.json` for every module that has one — permissive, regardless of `repos.lock.json` status. This makes the command useful for several workflows beyond the full-fleet path:

- **Cluster analysis.** Customer drops 5 module folders into a directory, runs `/archie-fleet-overview`, gets a 5-module subsystem view.
- **Existing-blueprints reuse.** Customer who has been running `/archie-deep-scan` on individual repos for months collects those folders, runs `/archie-fleet-overview`, gets a system view without paying to rescan.
- **Recovery rerun.** Customer fixes a previously-`UNAVAILABLE` module, runs `/archie-deep-scan` on it manually, deletes `FLEET_COMPLETE`, re-runs `/archie-fleet-overview`. Cheap retry point.

Dispatches a single Opus subagent (the overview agent) that synthesizes:

- System components (one Container per module, in C4 L2 terms)
- Cross-module edges (HTTP/REST + shared package imports — see Cross-module signal below)
- System-level architectural rules
- System-level pitfalls
- A coverage statement: which modules included, which excluded with reason

Outputs to `.archie/`:

- `overview-blueprint.json` — canonical fleet schema
- `overview-c4.md` — Mermaid C4 (`C4Context` + `C4Container` syntax, L1 + L2)
- `overview-scan-report.md` — ranked findings, same shape as `/archie-scan`'s `scan_report.md` at fleet level
- `AGENTS.md` — system-level memory consumable by Claude Code agents working in any module

When the four artifacts exist, touch `.archie/FLEET_COMPLETE`.

## Cross-module signal — v0 scope

The overview agent extracts cross-module relationships from per-module blueprints + light source spot-checks. v0 detects:

- **HTTP / REST calls.** Module A's outbound clients targeting module B's exposed routes.
- **Shared package / SDK imports.** Modules depending on a common library repo.

v0 explicitly does **not** detect (named in the report so customers see the limit honestly):

- Message-bus topics (pub/sub)
- gRPC contract sharing
- Cross-module DB sharing

These are v0.5+, contingent on customer feedback that the v0 report shape works.

The overview agent labels every edge with confidence and source citation. Edges it cannot ground in evidence are labeled `candidate`, never invented.

## Execution layer — the wrapper

CC sessions cannot self-resume past plan-window rate limits. A scheduler outside CC re-invokes it across windows. **Filesystem state is the resume engine** — every iteration re-reads disk, skips done work, and exits cleanly on any failure.

`archie-fleet-watch.sh` — a small bash wrapper, lock-protected, two-mode:

| Invocation | Behavior |
|---|---|
| `archie-fleet-watch.sh <system-dir>` | Self-loops; sleeps internally on failure, exits when `FLEET_COMPLETE` exists. For interactive Mac terminal use, walk-away ergonomics. |
| `archie-fleet-watch.sh --once <system-dir>` | Single iteration, exits. Used by external schedulers (launchd `StartInterval`, system cron, GH Actions self-hosted runner cron). |

The wrapper's loop body, regardless of mode:

1. If `.archie/FLEET_COMPLETE` exists → exit clean.
2. If `.archie/SCANS_COMPLETE` does NOT exist → invoke `claude -p "/archie-fleet-scan"`.
3. If `.archie/SCANS_COMPLETE` exists → invoke `claude -p "/archie-fleet-overview"`.
4. On any exit (success or failure): sleep, retry on next iteration.

A lock dir under `.archie/.fleet.lock/` (mkdir-based atomic primitive, with stale-PID detection) prevents two concurrent runs from clobbering each other if both modes are active (e.g., a CI cron and a local terminal both pointed at the same system folder).

The wrapper does not understand Archie. It only knows: invoke CC, watch for marker file, retry on exit. Every Archie-specific rule lives in the slash command directives — the wrapper changes only when retry / scheduling semantics change.

## Distribution

Same shape as today. New flag on the existing entry point:

```
npx -y @bitraptors/archie --install-fleet
```

Writes:
- `~/.local/bin/archie-fleet-watch.sh` (or platform-equivalent)
- `~/.claude/commands/archie-fleet-scan.md`
- `~/.claude/commands/archie-fleet-overview.md`

User-level slash commands, not project-level — system folders are working dirs the customer cycles through, not Archie-installed projects in the indie sense. The user-level location means `claude /archie-fleet-overview` works in any cwd.

## Build list

In implementation order:

1. **`archie/standalone/fleet.py`** — `prepare`, `validate`, `status` subcommands. Stdlib-only Python (zero deps, per existing convention).
2. **`.claude/commands/archie-fleet-scan.md`** — orchestrator slash command + per-module dispatch prompt block.
3. **`.claude/commands/archie-fleet-overview.md`** — orchestrator slash command + overview agent prompt (inline, mirroring `archie-deep-scan.md`'s convention of inline Wave-2 prompt at Step 5).
4. **Renderer extension** in `archie/standalone/renderer.py` — Mermaid C4 syntax, system-level scan report template, system AGENTS.md.
5. **`assets/archie-fleet-watch.sh`** — the wrapper. Shipped via npm package + installed by `--install-fleet`.
6. **`--install-fleet` flag** in `archie.mjs`.
7. **End-to-end test on a 3-module synthetic fleet** before exposing customers to real-scale runs.

Per memory `feedback_simplicity_first.md`, smallest viable shape only. No `fleet.yaml` metadata layer, no auto-clone-all helpers, no team/domain detection, no enforcement. Each is a v0.5+ decision contingent on customer feedback.

Per memory `feedback_feature_branches.md`, this work lives on `feature/multi-repo`. Main stays shippable for current Claude Code users at all times.

Per memory `feedback_iterative_over_batch.md`, the design IS iterative-by-construction — every per-module run is independent, every artifact is on-disk, every step is re-runnable.

Per memory `feedback_permission_audit.md`, before merging the slash-command additions: grep for inline python + bash not in the existing 29-entry allowlist, audit the permission shape.

## Honest unknowns to resolve before committing to implementation

These are the design-dependency questions that need real validation before code lands.

### 1. Nested Task dispatch

The per-module subagent dispatches its own Task subagents (Wave 1 parallel agents, Wave 2 reasoning agent — both inherent to deep-scan). Whether Claude Code's Task tool supports being called inside a Task subagent is the single biggest design dependency.

**Validation:** 1-module synthetic fleet test before going further. Spawn a Task subagent that itself runs `/archie-deep-scan` end to end; verify the resulting `.archie/blueprint.json`.

**Fallback if nesting fails:** the per-module subagent invokes the standalone Python scripts (scanner, merge, finalize) and makes Sonnet/Opus calls directly without spawning further subagents. More implementation work, avoids nesting. The fleet design otherwise unchanged.

### 2. Overview context size

N module blueprints fed to one Opus call. A 50-module fleet at typical blueprint sizes is plausibly within Opus's window, but plausibly is not measured.

**Validation:** measure on a real 10+ module fleet before declaring v0 done. If the synthesis quality degrades or the call fails, the v0.5 fix is hierarchical clustering: group modules (by directory cluster, by repos.txt section header, etc.), summarize each cluster, then meta-summarize.

### 3. `/tmp/` Wave-1 fragment durability across reboots

Per `archie-deep-scan.md:951`, Wave 1 outputs in `/tmp/archie_sub*_*.json` "may not survive a system reboot." A multi-day fleet run on a Mac that reboots could lose intermediate state.

The fleet's resume granularity is at the **module level**, not within a deep-scan. If a module's deep-scan dies anywhere, the next iteration sees no `blueprint.json` and re-runs the whole module from scratch. Coarser than within-deep-scan resume, acceptable as v0 cost. Would only revisit if real fleet runs show pathological re-work.

### 4. `$PROJECT_NAME` collision in `/tmp/`

Two concurrent module scans with the same repo basename clobber each other's Wave 1 fragments at `/tmp/archie_sub{1..4}_$PROJECT_NAME.json`. Slugs are unique by construction (derived from URL or path entry in `repos.txt`), so the per-module dispatch prompt **must** force `$PROJECT_NAME=<slug>` rather than letting deep-scan derive it from the basename. Documented as a hard requirement in the dispatch prompt.

### 5. Recovery reconciliation

When a customer manually deep-scans a module that was `UNAVAILABLE` at prepare time, that module's blueprint will exist on disk but `repos.lock.json` still says `UNAVAILABLE`. The overview agent should reconcile permissively: if `<module>/.archie/blueprint.json` exists, include it in the synthesis and emit a hint ("N modules manually recovered after prepare failure"). Lock file is a starting point, not the source of truth — disk is.

Symmetric: if a `<slug>/.archie/blueprint.json` exists for a slug not even in `repos.txt`, include it (the customer wanted it analyzed) and emit a hint ("1 module found on disk but not in repos.txt"). Cluster analysis becomes free this way.

## Workflow recovery

If the wrapper completes with some modules unavailable or scan-failed:

1. Customer fixes the upstream issue (auth, missing path, network).
2. Either path:

   **A. Full re-run.** Re-run `fleet.py prepare` to re-resolve, delete `SCANS_COMPLETE` and `FLEET_COMPLETE`, restart the wrapper. The wrapper scans newly-recovered modules, then re-runs overview.

   **B. Surgical recovery.** Manually scan recovered module: `cd <module> && claude /archie-deep-scan`. Delete only `FLEET_COMPLETE`. Run `claude /archie-fleet-overview` interactively. Skips the long batch entirely.

The two paths produce equivalent results. Path B is faster and is the recommended pattern for incremental recovery, especially when only one or two modules need fixing.

## Validation plan before declaring v0 complete

1. **Synthetic 3-module fleet test.** Three small repos, all known-good, mixed path + URL entries in `repos.txt`. Validates prepare, scan dispatch, marker transitions, overview synthesis, wrapper resume.
2. **Failure-mode test.** One module URL with bad auth; one path entry pointing to a non-existent dir. Validates `UNAVAILABLE` flow and that the rest still completes.
3. **Resume test.** Kill the wrapper mid-scan (after some modules complete, before all do). Restart. Verify it picks up cleanly without re-doing completed modules.
4. **Real-scale test.** A 10–15 module fleet from a real customer (with consent). Measures overview-context fit. If overview fits and renders coherently, v0 ships. If not, hierarchical clustering goes into v0.5 before exposing the report to buyers.

Step 4 is the gate that decides whether the v0 design is enough or whether the overview phase needs the hierarchical-clustering fallback before customer demos.
