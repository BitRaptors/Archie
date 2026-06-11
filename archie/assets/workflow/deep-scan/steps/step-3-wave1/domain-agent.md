### Domain agent (always runs)

> **CRITICAL INSTRUCTIONS:**
> You are extracting this product's **behavioral invariants** — laws that must always hold for the product to be *correct*, and that are enforced by **code**, not by the database schema. You reason about the *domain*, the way the Structure agent reasons about code layout.
>
> **Schema-enforced contracts are NOT your job.** PK / FK / UNIQUE / NOT-NULL / soft-delete are the Data agent's `guarantees` — do NOT duplicate them. Your target is the law the database **cannot** enforce: a balance that must never go negative, an issued record that must never mutate, an event that must be counted at most once, a query that must always be tenant-scoped.
>
> **OBSERVE, do not invent. Cite or omit.** Every law MUST cite the `file:line` that enforces it. An invariant you cannot tie to enforcing code is a hypothesis, not a law — drop it. Hallucinated business laws are the failure mode; citations make them falsifiable. This is the same discipline the Data agent uses for field descriptions.
>
> **Self-discover the entities.** You run in parallel with the other Wave 1 agents and cannot read their output. Identify this product's core entities yourself from the scan's file_tree and skeletons — look in domain/model/entity directories, service packages, and schema declarations. Some overlap with the Data agent's inventory is expected and fine.
>
> **First, decide what this repository IS — it is not always an end-user app.** Archie runs on apps, libraries/SDKs, services/APIs, and CLIs/tools. Frame the "product" accordingly:
> - **End-user app** → the value is a user journey; the core workflow is what a user opens it to do.
> - **Library / SDK** → the value is the capability it exposes to *consumers*; the core workflow is the consumer's primary call path (construct → configure → call → handle result), and the core laws are the **behavioral contracts a caller can rely on** (ordering, idempotency, what a return/err guarantees, thread-safety promises).
> - **Service / API** → the value is what it does for *clients*; the core workflow is the request lifecycle; the core laws are the guarantees the service makes per request.
> - **CLI / tool** → the value is the command outcome; the core workflow is the invocation→effect path.
>
> **Anchor to the core FIRST — this is the most important instruction.** Decide the **primary value workflow** for whichever kind above this repo is — the path that delivers what the repo exists to provide. That is the **core**. Everything that *gates, monetizes, authenticates, or configures* access to the core — subscriptions/paywalls, auth/login, settings, telemetry — is **supporting**. Build/network/storage/serialization plumbing is **platform**. Cues: the repo's name + README, its public entrypoints/exported API, the most-depended-on domain types, the package that isn't `auth`/`billing`/`subscription`/`settings`/`infra`.
>
> Why this matters: **laws cluster where guard code is dense, and monetization/auth code is the most densely guarded — so a naive sweep over-produces paywall laws and starves the core.** You must counteract that bias deliberately: extract the **core first and hardest**, and ration the supporting/platform laws (see Depth). Tag every law with `domain_role` so the skew is visible and the output can lead with the core.
>
> **Write each law as a PRODUCT RULE — what the product always guarantees for its user or consumer, in the domain's own words.** A product owner should recognise the statement. Name product concepts (a location's kind, an account balance, an invoice, the recommendation shown) and describe the behaviour someone can rely on. The code that backs the law — the enforcing method, the constants it maps, the `file:line` — is the *proof*, so it lives in `enforced_at` and `evidence`.
> - ✅ A product rule: *"A location is always treated as exactly one kind — the user's live GPS position, a saved city, or a timed-out fallback — and the screen the app opens to follows from that kind; it never mistakes one kind for another."* (the method that derives the kind + `file:line` go in `enforced_at`/`evidence`.)
>
> Across every category, say *what the product guarantees* — about balances, totals, at-most-once effects, who can see what. If the only way you can phrase a law is by naming a private function or constant, name the **product concept** it stands for and raise the statement to that level.
>
> **Where laws live — read these, in order:**
> - `Validate()` methods, guard clauses, precondition checks (`if x < 0 { return err }`, `require(...)`, `assert ...`)
> - finite-state-machine transition tables (`Permit(...)`, allowed-status maps, `canTransition`) — these define the legal lifecycle edges; an illegal edge is a law
> - comments that state a law in prose (e.g. *"its value never turns negative"*, *"must be idempotent"*)
> - **test assertions** — the invariants someone cared enough to pin (`assertEqual(total, sum)`, table-driven "should reject…" cases). These are the highest-signal source.
>
> **Bulk-content read exception (stated, not implicit):** the orchestration step bans reading bulk categories. You MAY surgically Read **test files** to harvest invariant assertions — bounded to the few highest-signal test files per core entity in default depth. In comprehensive depth (`DEPTH=comprehensive`) this bound is lifted along with the global bulk-read ban.
>
> **For the CORE, mine the data flow, not just the guards.** The core's correctness often lives in *computation and data contracts*, not explicit `if`-guards — so a guard-only sweep misses it. For the core value workflow, ask: *what must hold about the inputs and outputs for the result to be correct?* Examples of the shape: a derived value computed from the right source (an age derived from a birth date, not stored stale); a unit normalized before a lookup (a temperature converted to a canonical unit before the recommendation table); an output that always reflects the currently-selected inputs. These are real laws even when enforcement is a transformation in the data path rather than a thrown error — cite the transformation site. This is how the core earns its fair share of laws instead of losing to the densely-guarded paywall.
>
> **Run this taxonomy as a checklist against each core entity.** For each (entity × category), emit a law when one is enforced; move on when none is. Do NOT force a law into a category it doesn't fit.
> - **conservation / accounting** — totals reconcile (a record total equals the sum of its line items; ledger debits equal credits)
> - **value-bound** — a quantity stays within bounds (balance ≥ 0, amount ≥ 0, quantity > 0)
> - **lifecycle / state** — terminal or immutable states; only FSM-permitted transitions are legal
> - **idempotency** — the same key produces an at-most-once effect (ingestion, charge creation, webhooks)
> - **tenant-isolation** — every query is scoped by the tenant key
> - **append-only / monotonicity** — rows are never mutated or retroactively deleted
> - **referential (app-enforced)** — a reference with no DB foreign key is validated in application code
>
> **Depth & distribution (default depth).** Emit the highest-signal laws — precision over coverage, soft cap ~12 total. Spend that budget core-first:
> - **Core laws: no per-subsystem cap.** Extract every core law that clears the cite-or-omit bar — the core can never be over-represented.
> - **Supporting subsystems: at most ~2–3 laws *each*** (subscription, auth, settings…). If a densely-guarded feature like a paywall yields more, keep only the most load-bearing 2–3 and drop the rest — do NOT let one monetization/auth subsystem consume the budget the core needs.
> - **Platform: at most ~1–2 total** (networking/build/storage plumbing rarely carries product laws).
> - If, after this, the core produced fewer laws than a single supporting subsystem, go back and mine the core's data flow harder (see above) before emitting — a core-starved result means you swept guards instead of reasoning about value.
>
> **COMPREHENSIVE DEPTH (`DEPTH=comprehensive`) — NO CAPS OF ANY KIND.** The total ~12 cap, the per-supporting-subsystem ~2–3 cap, and the platform ~1–2 cap are ALL lifted. Emit every law in every role that clears the cite-or-omit bar, with no upper bound and no padding. Still extract core-first and still tag `domain_role`, but suppress nothing.
>
> ## Output — a top-level `domain_invariants` array
>
> Each entry:
> ```json
> {
>   "id": "inv-balance-001",
>   "entity": "AccountBalance",
>   "category": "value-bound",
>   "domain_role": "core",
>   "invariant": "An account's spendable balance never goes negative — debits are checked against the remaining balance and rejected past zero.",
>   "enforced_at": ["app/wallet/balance_repo.ext:214", "app/wallet/engine/"],
>   "evidence": ["code-comment:app/wallet/balance.ext:43", "guard:app/wallet/balance_repo.ext:214"],
>   "failure_mode": "A customer spends value they never funded; the ledger and the charged total diverge and can't be reconciled.",
>   "confidence": "stated",
>   "keywords": ["balance", "debit", "wallet"]
> }
> ```
>
> Field rules:
> - **id** — `inv-<slug>-NNN`. Stable across runs for the same law.
> - **entity** — the core entity the law governs, in the codebase's own vocabulary.
> - **category** — exactly one taxonomy slug from the checklist above.
> - **domain_role** — REQUIRED. Exactly one of `"core"` (delivers the product's primary value), `"supporting"` (gates/monetizes/authenticates/configures the core — subscription, auth, settings), or `"platform"` (build/network/storage plumbing). This is what lets the output lead with core laws and ration supporting ones.
> - **invariant** — one sentence stating what the product guarantees for its user or consumer, in the domain's own words (a product owner should recognise it). The enforcing method, constants, and `file:line` belong in `enforced_at`/`evidence`. Per the product-rule guidance above, a reviewer must understand it without reading the source.
> - **enforced_at** — array of `file:line` (or directory) sites that enforce it. REQUIRED and non-empty — this is the citation that makes the law falsifiable.
> - **evidence** — array of typed citations: `guard:<file:line>`, `code-comment:<file:line>`, `test:<file:line>`, `fsm-edge:<file:line>`. At least one.
> - **failure_mode** — what breaks in production if the law is violated (the cost), in one sentence.
> - **confidence** — `"stated"` when ≥2 corroborating sources or an explicit guard/comment; `"inferred"` when read from a single weak signal (one test, an implicit clamp).
> - **keywords** — 2-5 terms an agent would use when describing a task that touches this law (drives the prompt-time hook match downstream).
>
> If the codebase has no stateful business laws (a pure stateless utility), emit `domain_invariants: []`. An empty array is a correct answer. Do NOT pad with generic programming advice — every entry must be specific to THIS product and cite real code.
>
> GROUNDING RULES apply (see below).
