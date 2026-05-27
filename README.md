# Archie — AI Governance for Coding Agents

[![npm version](https://img.shields.io/npm/v/@bitraptors/archie)](https://www.npmjs.com/package/@bitraptors/archie)
[![GitHub release](https://img.shields.io/github/v/release/BitRaptors/Archie)](https://github.com/BitRaptors/Archie/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Your AI agent is fast on day 1. By week 3, it's putting files in the wrong layer, re-implementing helpers that already exist, and quietly drifting from the architecture you carefully explained at the start. The codebase erodes; the speed advantage fades.

Archie scans your repo and builds a **semantic blueprint** — not a file index or a vector dump, but the architectural *reasoning* behind the code. Why JWT instead of sessions. Why `ApiClient` is a singleton. Which pattern to use for cross-cutting concerns. What's already been tried and abandoned. The blueprint loads passively into every coding-agent session via CLAUDE.md and AGENTS.md (root + per-folder), so your agent walks in **already knowing the architecture** — no grep tours, no re-derivation of intent from code, no repeating the mistakes the team already burned through.

**What's in the blueprint** (out-of-the-box context at session start, queryable in-session):

- **Decisions** — the choice, the *why*, the trade-off, and what was rejected
- **Components** — purpose, responsibility, public interface, dependencies
- **Communication patterns** — when to use which, with a selection guide
- **Pitfalls** — class-of-problem warnings + concrete past incidents
- **Implementation guidelines** — how features were actually built in *this* repo (libraries, key files, usage examples)
- **Rules** — enforced at edit time, carrying inline semantic content (severity class, rationale, canonical example, links back to the motivating decision)

**Per-folder Intent Layer.** Archie also writes a `CLAUDE.md` inside *every significant folder*, distilling the blueprint down to just what matters for files there: which patterns this folder uses, what belongs here vs. elsewhere, the anti-patterns specific to this layer, the key files with modification notes. When the agent opens `src/api/routes/`, Claude Code (and Codex via `AGENTS.md`) auto-loads that folder's context — the agent already knows the local conventions before it touches a single file. No `Glob`, no `Grep`, no "let me first read a few files to understand the pattern" round-trips. The context for the work is always already in scope.

Pre-tool-use hooks are the active gate — when the agent tries to write a file that violates a decision, the hook exits with the rule plus the architectural reason, and the agent retries. The reason it can do this without a separate lookup round-trip is that the *why* lives inside the rule, derived from the semantic blueprint.

Works with any language. Zero runtime dependencies for standalone scripts.

**Coding-agent harness support:** Archie targets two CLIs — **Claude Code** (stable, primary target) and **OpenAI Codex CLI** (🚧 BETA — may contain errors). One workflow, rendered per-CLI at install time. See [Multi-CLI Support](#multi-cli-support) below.

## How It Works

A multi-wave AI pipeline produces a structured `blueprint.json` (decisions, components, pitfalls, rules) from your repo. The **Intent Layer** (opt-in) then projects the blueprint per-directory, writing a `CLAUDE.md` into every significant folder so agents auto-load the local conventions the moment they work there — zero exploration round-trips. At edit time, seven hooks gate the coding agent — blocking decision violations, warning on trade-off undermines, informing on pattern divergence. Findings compound across scans (id-stable upserts, novelty escalation), and deep-scans are resumable via `--incremental`, `--continue`, and `--from N`.

Full pipeline, data model, per-CLI render maps, and connector contracts: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Install

```bash
npx @bitraptors/archie /path/to/your/project
```

Interactive multi-select with detected CLIs pre-selected. Copies standalone scripts + hook scripts, renders the workflow per CLI, writes shims and hook bindings, patches `~/.codex/config.toml` non-destructively, drops `.archieignore` / `.archiebulk` / `.gitignore` entries. Upgrades replace in place. The first Archie command asks once about anonymous telemetry (opt-in).

Skip the picker with `--target=all` / `--target=auto` / `--target=claude` / `--target=codex` / `--target=claude,codex`. Non-TTY stdin (CI) defaults to `--target=all`.

## Commands

| Command | What it does | Time |
|---------|-------------|------|
| `/archie-deep-scan` | Comprehensive baseline. 2-wave multi-agent analysis (Sonnet fact-gatherers + Opus reasoner) producing blueprint, optional per-folder CLAUDE.md, rules, findings, pitfalls, health. Supports `--incremental`, `--continue`, `--from N`, `--reconfigure`. | 15-20 min (full), 3-6 min (incremental) |
| `/archie-intent-layer` | Standalone per-folder CLAUDE.md regeneration. Asks Full / Incremental / Auto upfront. Requires `blueprint.json`. | 3-15 min |
| `/archie-share` | Upload blueprint + findings + scan report to a hosted viewer. Default (BitRaptors Supabase), enterprise stored-credentials (BYO S3), or enterprise paste-presigned-URL — see [Enterprise Share](#enterprise-share). | seconds |
| `/archie-viewer` | Local blueprint inspector. Runs the same React UI as the hosted share viewer at `localhost:5847/local` — no upload, all data stays on your machine. | seconds |

Run `/archie-deep-scan` once for the baseline, then `/archie-deep-scan --incremental` after code changes to refresh the analysis.

### `/archie-deep-scan` in action

![archie-deep-scan demo](docs/assets/archie-deep-scan-demo.gif)

<details>
<summary>Example deep-scan summary</summary>

```
  Archie Deep Scan — Complete Assessment

  Generated:  26 blueprint sections, 20 components, 63 rules, 496 per-folder CLAUDE.md,
              1,200 source files scanned, 476 dependencies mapped.

  Health:     Erosion 0.95 (front) / 0.69 (back) · Gini 0.92 / 0.76 · LoC 76,903 / 45,261

  Drift:      14 errors (raw ipcRenderer exposure, API key in logs, duplicate startup
              handlers, stale WebSocket closures, DI-layer imports from utils, …)
              14 warnings (sync I/O in async paths, monolith routers, compat-hook CRUD leak, …)

  Top risks:  IPC security hole · API key exposure · stale WebSocket state ·
              circular deps & layer violations · duplicate startup handler

  Semantic duplication: 3 groups (placeholder_resolver clone, dual WebSocketMappingService,
                                  sidebar state in two contexts)

  Archie is now active. Rules will be enforced on every code change.
  Run /archie-deep-scan --incremental after code changes to refresh the analysis.
```

</details>

## Key Features

- **Monorepo-aware** — auto-detects sub-projects (Gradle / package.json / Cargo.toml / pyproject.toml / …) and asks once for scope: **whole**, **per-package**, **hybrid**, or **single**. Persisted in `.archie/archie_config.json`.
- **Three-tier ignore** — `.gitignore` (skipped) · `.archieignore` (skipped, Archie-specific) · `.archiebulk` (**scanned but opaque** — records path + `{category, framework}` without reading contents, so 248 Android layouts don't burn analytical budget).
- **Compounding findings** — id-stable upserts across runs: recurring findings bump `confirmed_in_scan`, resolved ones flip `status`, Wave-2 reasoning escalates draft findings to canonical.
- **Resumable deep-scans** — `--incremental` (changed files, 3-6 min), `--continue` (resume after interruption), `--from N` (specific step).
- **Rules with semantic content** — every rule carries `severity_class`, `why` (copied from motivating decision), `example`, and `forced_by`/`enables`/`alternative` links. Pre-edit hook reads `severity_class` to gate: blocking, warning, or informational.

## Health Metrics

`/archie-deep-scan` tracks architecture health over time in `.archie/health_history.json`:

| Metric | What it measures |
|--------|-----------------|
| **Erosion** (0-1) | Fraction of complexity mass in high-CC functions (>10). 0 = even, 1 = god-functions. |
| **Gini** (0-1) | Inequality of complexity distribution. 0 = every function equally complex. |
| **Top-20% share** (0.2-1) | Fraction of total complexity in the largest 20% of functions. |
| **Verbosity** (0-1) | Duplicate-line ratio across source files. |
| **Abstraction waste** | Count of single-method classes and tiny wrapper functions. |
| **LOC** | Total lines of code — monotonic growth without features signals decay. |

## Enterprise Share

For teams whose InfoSec policy blocks uploading to third-party infrastructure, `/archie-share` supports two enterprise modes alongside the default Supabase upload:

- **Stored credentials** — `python3 .archie/share_setup.py --bucket … --region … --access-key-id … --secret-access-key …` writes `~/.archie/share-profile.json` (chmod 600). Uploads land directly in your S3 bucket via sigv4-signed PUT (stdlib only, no boto3). BitRaptors stores nothing — the viewer fetches from your bucket via a URL fragment (never transmitted to any server).
- **Paste presigned URL** — no credentials stored. InfoSec mints a per-share presigned PUT URL on demand, dev pastes it into `/archie-share`. Strongest audit story.

Setup walkthrough (CORS template, IAM policy, step-by-step): **[docs/enterprise-share-setup.md](docs/enterprise-share-setup.md)**.

## Multi-CLI Support

Archie targets **Claude Code** (Anthropic, stable, primary target) and **OpenAI Codex CLI** (🚧 BETA — may contain errors) through one connector framework.

**One workflow, rendered per-CLI at install time.** A canonical template under `archie/assets/workflow/<command>/` renders into `<project>/.archie/workflow/<cli>/` — each copy reads natively in its host CLI. Both invoke the same Python scripts and the same canonical hook scripts under `.archie/hooks/`; the per-CLI rendering is only the *surface* (model name, tool names, dispatch style).

**Permissions are pre-wired from a shared catalogue** (`archie/manifest_data.py::COMMAND_RULES` + `_STANDALONE_SCRIPTS`), so the scan command surface is auto-approved and the user isn't prompted mid-run. Mutating git, the one-time `/archie-share` network-egress prompt on Codex, and anything outside the catalogue stay interactive by design.

|  | Claude Code (stable) | Codex CLI (🚧 BETA) |
|---|---|---|
| **Workflow surface** | `Opus`, `Agent tool`, `AskUserQuestion` | `gpt-5`, native Codex subagents, direct conversation prompts |
| **Permissions file** | 27-entry `.claude/settings.local.json` allow-list | 53 Starlark `prefix_rule(decision="allow", …)` entries in `<project>/.codex/rules/archie.rules` (validated via `codex execpolicy check`) |
| **Custom subagent** | Agent tool (built-in) | Project-scoped at `<project>/.codex/agents/archie-analysis.toml` |
| **Config patches** | None | `~/.codex/config.toml`: `[agents] max_threads/max_depth` + `[projects."<abs>"] trust_level = "trusted"` (set-if-absent, so the project-scoped `.codex/` layer actually loads — per Codex docs, untrusted projects skip that layer entirely) |
| **Parallel fan-out** | Agent-tool subagents (Wave 1, Intent Layer, monorepo workspaces) | Native Codex subagents — workflow asks Codex in natural-language prose to spawn `archie_analysis` per task |
| **Sandbox** | Default | Workspace-relative artifacts (`.archie/tmp/archie_*.json`) covered by `workspace-write`, no widening |

> **🚧 Codex CLI is BETA and may contain errors.** Static install artifacts are validated by the test suite (every install produces every expected file). The runtime path is not exhaustively validated: natural-language subagent invocation under different Codex versions, execpolicy enforcement, sandbox / approval / hook-trust interactions across `codex exec` non-interactive mode and interactive sessions. **Pin Claude Code for production scans. Treat Codex as evaluation** — and please flag any unexpected prompt or behaviour so we can patch the catalogue / wording.

## Requirements

- **Python 3.9+** for standalone scripts (installed via `npx @bitraptors/archie`, stdlib only, zero pip dependencies)
- **Node.js 18+** for `npx @bitraptors/archie` installer
- A supported coding-agent harness:
  - **Claude Code** — stable, primary target
  - **OpenAI Codex CLI** — beta

  The same `archie-deep-scan` / `archie-intent-layer` / `archie-share` / `archie-viewer` commands run in both harnesses with feature parity (subject to each harness's API ceiling — see [Multi-CLI Support](#multi-cli-support)).

## Telemetry & update checks (anonymous, opt-in)

Opt-in (three tiers: **community** / **anonymous** / **off**), asked once on first command via a model-driven prompt. Collected: command name, version, OS/arch, per-step durations, detected stack categories, CLI flavor (`claude` / `codex` / `unknown`). **Never collected**: source code, file paths, repo names, blueprint contents. Local log at `~/.archie/analytics/runs.jsonl`. Update checks (also opt-in, default on) hit `registry.npmjs.org` — no Archie infrastructure involved.

```bash
python3 .archie/analytics.py 7d                   # see your local activity
python3 .archie/config.py set telemetry off       # opt out
python3 .archie/update_check.py snooze            # snooze update hints
```

Full details (ingest endpoint, RLS policy, payload shapes): **[docs/ARCHITECTURE.md#telemetry](docs/ARCHITECTURE.md#telemetry)**.

## Kudos for Inspiration

- **[Cartographer](https://github.com/kingbootoshi/cartographer)** by [@kingbootoshi](https://github.com/kingbootoshi)
- **[Graphify](https://github.com/safishamsi/graphify)** by [@safishamsi](https://github.com/safishamsi)
- **[SlopCodeBench](https://arxiv.org/abs/2603.24755)**

## License

MIT
