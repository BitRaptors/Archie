# Shared fragment — Semantic Findings calibration spec

> **This file is the single source of truth for the Semantic Findings schema, severity rubric, and quality gate.**
> Every agent prompt that emits Semantic Findings MUST reference this file by path and follow it exactly.
> When you update calibration, update this file ONLY — do not restate calibration inline in any agent prompt.
> Changes here apply to both `/archie-scan` and `/archie-deep-scan` automatically.

> **Normative terms:** `MUST` / `MUST NOT` / `SHOULD` / `SHOULD NOT` are used in the RFC-2119 sense. Blockquotes mark normative directives; prose is descriptive.

---

## 1. Output schema

Every Semantic Finding — systemic or localized, draft or canonical, regardless of producer — conforms to the following shape:

```json
{
  "id": "sf-<hash>",
  "category": "systemic | localized",
  "type": "<from taxonomy — see section 5>",
  "severity": "error | warn | info",
  "scope": {
    "kind": "system_wide | cross_component | within_component | single_file",
    "components_affected": ["..."],
    "locations": ["path/to/file:symbol:line", "..."]
  },
  "pattern_description": "one-sentence architectural name — required for systemic, omitted for localized",
  "evidence": "concrete instances (systemic) or single-location detail (localized)",
  "root_cause": "mechanistic explanation — names the structural reason (e.g., missing abstraction, conflicting decisions, organic growth without refactor, erosion trajectory)",
  "fix_direction": "actionable — extract X / consolidate to Y / split Z / add middleware W",
  "blueprint_anchor": "decision:D.3 | trade_off:T.2 | pitfall:P.5 | null",
  "blast_radius": 22,              // systemic-only; count of components / files affected
  "blast_radius_delta": 7,         // systemic-only; change vs prior scan (0 if new or unchanged)
  "lifecycle_status": "new | recurring | resolved | worsening",
  "synthesis_depth": "draft | canonical",
  "source": "wave1_structure | wave1_patterns | wave2 | phase2 | fast_agent_a | fast_agent_b | fast_agent_c | mechanical"
}
```

Field population rules:

- **Producing agent populates** all fields except `lifecycle_status` and `blast_radius_delta`.
- **Aggregator populates** `lifecycle_status` and `blast_radius_delta` (not the agent).
- **Required for systemic:** `blast_radius` and `blast_radius_delta`. Optional for localized.
- **`id`** is assigned by the aggregator if the agent doesn't emit one.

---

## 2. Quality gate (hard requirement)

A candidate finding that can't fill all required fields is **dropped**. No exceptions. This is the only filter — there are no count caps (see section 8).

| Field | Systemic | Localized |
|---|---|---|
| `pattern_description` | required | omit |
| `evidence` instances | ≥3 concrete locations | 1 concrete location |
| `root_cause` | required, mechanistic | required |
| `fix_direction` | required, actionable | required |
| `blast_radius` | required | optional |
| `blueprint_anchor` | populate when applicable | populate when applicable |

### 2b. What "mechanistic" and "actionable" mean

- **Mechanistic** — the `root_cause` names the structural reason (e.g., missing abstraction, conflicting decisions, organic growth without refactor, erosion trajectory), not the symptom.
- **Actionable** — `fix_direction` names a concrete move (e.g., extract / consolidate / split / add middleware), not a goal (improve / clean up / consider refactoring).

---

## 3. Severity rubric

Severity is assigned by the producing agent using these rules. Apply the **highest** matching rule — do not average.

- Cross-layer violation OR cycle crossing a documented boundary → `error`
- Cyclomatic complexity ≥ 50 → `error`; 25–49 → `warn`; 10–24 → `info`
- Match against a blueprint `violation_signals` entry → `error`
- Active manifestation of a documented pitfall → `error`
- `dependency_magnet` with fan-in > 20 OR a rising trajectory → `error`
- ≥3 near-twin instances of `semantic_duplication` OR any instance in a security-critical path → `error`

**Default when no rule matches:** `info` for localized findings; `warn` for systemic findings with `blast_radius ≥ 5`.

---

## 4. Type taxonomy

All findings carry a `type` from one of the two lists below. Category is implied by type — do not emit a `localized` finding with a systemic type, or vice versa.

### 4a. Systemic types (9)

Overarching issues spanning ≥3 locations or multiple components.

- **`fragmentation`** — The same concern is implemented in multiple places with divergent approaches, rather than through one shared mechanism (e.g., auth enforcement spread across middleware, decorators, and inline checks).
- **`god_component`** — A single component accumulates responsibilities from unrelated domains, becoming a dependency sink that distorts the architecture around it (e.g., a `shared/` package imported by every layer for auth, storage, UI, and logging).
- **`split_brain`** — Two or more components own overlapping state or logic without a designated source of truth, creating ambiguity about which is authoritative (e.g., user profile fields read from both the API client cache and the local store).
- **`erosion`** — A previously clean pattern or boundary has been progressively weakened by incremental deviations, each individually small but collectively undermining the original design.
- **`missing_abstraction`** — A recurring shape of code or data exists across the codebase but has never been lifted into a named concept, forcing every caller to re-implement the same protocol (e.g., error-handling flow repeated in every route).
- **`inconsistency`** — Equivalent operations are expressed with materially different conventions across components, with no architectural rationale for the divergence (e.g., some services use repositories, others reach into the ORM directly).
- **`trajectory_degradation`** — Quantitative health signals (complexity, coupling, file size, duplication) show a clear worsening trend over time in a defined area of the codebase.
- **`boundary_violation`** — Code systematically ignores a documented architectural boundary (layer, module, package, bounded context) from ≥3 call sites, not as isolated mistakes but as a normalized pattern.
- **`responsibility_diffusion`** — A single logical responsibility is split across so many collaborators that no component can be said to own it, and reasoning about changes requires tracing through the whole chain.

### 4b. Localized types (12)

Location-specific issues with 1 concrete site.

- **`decision_violation`** — A specific location contradicts a concrete blueprint decision (e.g., code calls the DB directly when decision D.3 mandates the repository layer).
- **`trade_off_undermined`** — A specific location re-introduces the cost that a documented trade-off was meant to eliminate (e.g., adds a synchronous call in a path that was made async to meet latency goals).
- **`pitfall_triggered`** — A specific location instantiates the exact shape described by a documented pitfall (e.g., pitfall P.5 warns against storing tokens in localStorage; this file does).
- **`responsibility_leak`** — A concrete symbol carries logic that belongs to a different component by the blueprint's responsibility assignment (e.g., a view handler performs data validation owned by the domain layer).
- **`abstraction_bypass`** — A concrete call site skips an existing abstraction to reach an underlying primitive directly (e.g., one caller uses raw `fetch` while the rest go through the API client).
- **`semantic_duplication`** — Two or more concrete functions/blocks implement the same behavior with near-identical structure but different names or surface syntax, not caught by a textual duplication scan.
- **`pattern_erosion`** — A single file deviates from the pattern documented in its folder's `CLAUDE.md` (e.g., the folder prescribes a hook-based API but this file exposes a class).
- **`dependency_violation`** — A specific import or call crosses a documented dependency boundary the wrong way (e.g., `apps/webui` imports from `apps/electron/src/...`).
- **`cycle`** — A concrete import cycle exists between named modules or packages.
- **`complexity_hotspot`** — A specific function or file whose complexity exceeds the threshold defined in section 3 and is large enough to matter for maintenance.
- **`rule_violation`** — A specific site breaches a rule defined in `rules.json` or `platform_rules.json` (the mechanical rules layer).
- **`pattern_divergence`** — A single site diverges from a structural pattern that `drift.py` or Agent C detects as the dominant convention in the codebase.

Note on overlap: `fragmentation` (systemic) is the *pattern* of many divergent implementations; `pattern_divergence` (localized) is a *single site* that differs from the dominant convention. `inconsistency` (systemic) and `fragmentation` differ in intent — `fragmentation` is about the same concern being solved multiple ways; `inconsistency` is about equivalent operations being expressed differently. When in doubt, prefer the type that most directly names the architectural harm.

---

## 5. Synthesis depth

Every finding carries `synthesis_depth`, signalling how deep the producing agent's synthesis could go given its context budget.

- **`draft`** — Shallower synthesis. `root_cause` may be observational ("many places call X directly"); `fix_direction` may be generic ("consolidate into a helper"). Emitted by fast-scan agents and Wave 1 structure/patterns agents, which run cheap and wide.
- **`canonical`** — Authoritative synthesis. `root_cause` traces to blueprint decisions/pitfalls/trade-offs and historical context; `fix_direction` is sequenced and names specific components. Emitted by Wave 2 (Opus) only.

### 5a. Which agent writes which depth

| Agent / producer | Depth | `source` string |
|---|---|---|
| Fast-scan Agent A (`/archie-scan`, structure / dep graph) | `draft` | `fast_agent_a` |
| Fast-scan Agent B (`/archie-scan`, health / complexity) | `draft` | `fast_agent_b` |
| Fast-scan Agent C (`/archie-scan`, rules / patterns) | `draft` | `fast_agent_c` |
| Wave 1 Structure (`/archie-deep-scan`) | `draft` | `wave1_structure` |
| Wave 1 Patterns (`/archie-deep-scan`) | `draft` | `wave1_patterns` |
| Shrunk Phase 2 (`/archie-deep-scan`: `semantic_duplication` + `pattern_erosion`) | `draft` | `phase2` |
| Wave 2 reasoning (`/archie-deep-scan`, Opus) | `canonical` | `wave2` |
| `drift.py` (mechanical) | `draft` | `mechanical` |

### 5b. Upgrade pass

Wave 2 re-processes stored `draft` findings whose `lifecycle_status` is `recurring`, enriches `root_cause` and `fix_direction`, and flips `synthesis_depth` to `canonical`. The upgrade pass is the only mechanism that changes an existing finding's depth — never edit the field by hand or in an agent prompt.

---

## 6. Source string enum

The `source` field names the producing agent. Exactly the 8 values enumerated in the section 5a table are valid; any other value is a bug and the aggregator will reject the finding.

---

## 7. Blueprint anchor

`blueprint_anchor` references a specific element of `blueprint.json` using the form `decision:D.3`, `trade_off:T.2`, or `pitfall:P.5`. Set it whenever the finding directly corresponds to a blueprint element (a violated decision, an undermined trade-off, a triggered pitfall). Set to `null` when no such correspondence exists. This is the field the viewer uses to render the two-way link from a decision to the findings tagged to it.

---

## 8. No count caps

**Emit every finding you can substantiate with concrete evidence. No cap. Do not invent to pad. Do not drop to stay under a count. The quality gate is the only filter.**

Agents that over-emit low-quality candidates will have them dropped at the quality gate; agents that under-emit will miss real issues. Trust the gate; don't second-guess yourself on count.

<!-- Maintainer note: every agent prompt that used to say "Emit 3-5 findings" or similar must be migrated to quote the bold directive above verbatim. -->

---

## 9. Good vs bad examples

The quality gate's "mechanistic" and "actionable" bars are best communicated by example. Below, each pair shows a finding rejected for fluffiness and the same finding written to the bar. Use the second as your target when writing `pattern_description`, `root_cause`, and `fix_direction`.

### 9a. `pattern_description` (systemic)

**Bad** — restates the symptom, no architectural name:
> `"There are several places where authentication is handled differently."`

**Good** — names the architectural shape in one sentence:
> `"Auth enforcement is fragmented across 7 call sites using 3 incompatible mechanisms (middleware, decorator, inline check), with no single point of policy."`

### 9b. `root_cause` (all findings)

**Bad** — observational, doesn't explain *why the structure is this way*:
> `"Many files bypass the API client and use fetch directly."`

**Good** — mechanistic, traces to a structural reason:
> `"The API client was introduced after ~40% of call sites were already written with raw fetch; decision D.7 mandated the client for new code but did not require migration, so the two patterns coexist indefinitely and new contributors copy whichever they see first."`

### 9c. `fix_direction` (all findings)

**Bad** — vague goal, no sequenced move:
> `"Consider refactoring to use the API client everywhere for consistency."`

**Good** — sequenced, names the specific steps:
> `"(1) Add a lint rule in platform_rules.json forbidding raw fetch outside packages/api-client. (2) Migrate the 6 call sites under apps/webui/src/admin/ first (smallest cluster). (3) Tackle apps/electron/src/ in a second pass — expect touch in auth.ts, storage.ts, sync.ts."`

### 9d. Draft vs canonical on the same finding

This pair illustrates the `draft → canonical` quality difference; use it when calibrating Wave 2 upgrade-pass enrichment.

**Draft** (acceptable at draft tier, but shallow):
> `root_cause: "Auth handling is scattered across the codebase without a central enforcement point."`
> `fix_direction: "Consolidate auth checks into middleware."`

**Canonical** (target for Wave 2):
> `root_cause: "Three successive decisions (D.2 API middleware, D.5 per-route decorators for admin, D.9 UI-level guards for optimistic rendering) each introduced a new enforcement site without deprecating the prior one. The resulting stack is cumulative, not layered: every request passes through all three, and removing any one silently weakens coverage in a non-obvious subset of routes."`
> `fix_direction: "(1) Choose middleware as the single enforcement tier (simplest to reason about, already covers 80% of routes). (2) Rewrite the 12 admin routes under apps/webui/src/admin/api/ to rely on middleware claims rather than the decorator. (3) Remove the UI-level guard from apps/webui/src/components/ProtectedRoute.tsx once middleware is canonical — keep only the optimistic redirect. (4) Add a platform rule forbidding new uses of the decorator to prevent regrowth."`

The canonical version names the specific decisions, explains why the structure is cumulative rather than layered, and sequences the fix with concrete file paths. That is the bar for `wave2` findings and for `draft` findings upgraded by the Wave 2 upgrade pass.
