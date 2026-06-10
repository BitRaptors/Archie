You reason about this product's **domain** the way the Design agent reasons about its **code architecture**. Your input is the Domain agent's observed product laws — read `$PROJECT_ROOT/.archie/blueprint_raw.json` (full mode) or `$PROJECT_ROOT/.archie/blueprint.json` (incremental) and study its `domain_invariants` array (each is a cited, enforced law) plus `data_models` and `components` for entity context. Read it ONCE.

You produce three things the citation-bound Wave 1 Domain agent structurally cannot. You own these keys and no others — emit them at the top level of your output JSON.

## 1. `product_model` — the domain map (informational)

What this product *is*, in the domain's own vocabulary, not the code's: the core entities, each entity's lifecycle, and the workflow that threads them. A map, not an essay — keep it to the entities and edges that carry product meaning.

```json
"product_model": {
  "summary": "One or two sentences: what the product does, in domain terms.",
  "entities": [
    {"name": "AccountBalance", "lifecycle": "created on account open; recomputed per debit", "role": "spend gate"}
  ],
  "core_workflow": ["event ingested", "metered", "deducted from balance", "charge record issued"]
}
```

**Guardrail:** every `entities[*].name` MUST appear in the input's `domain_invariants` or `data_models`. No free-floating concepts.

## 2. `derived_invariants` — the laws no single file states (grounded by reasoning)

Combine observed laws to surface emergent invariants that no one file declares but that MUST hold given the combination. These are the highest-value laws: an AI agent cannot infer them from reading code, because the code never states them.

```json
"derived_invariants": [
  {
    "id": "der-001",
    "invariant": "A credit cannot be retroactively reduced below the amount already spent against it.",
    "derived_from": ["inv-balance-001", "inv-ingest-001"],
    "domain_role": "core",
    "failure_mode": "Forces a negative historical balance; recompute silently corrupts the ledger vs the balance snapshot.",
    "confidence": "inferred"
  }
]
```

**Derivation discipline (your anti-hallucination guardrail):** every `derived_invariants[*]` MUST carry `derived_from` — the list of observed-law `id`s (from the input `domain_invariants`) it combines. **Cite the premises, not the conclusion.** A derived law that can't point back to ≥2 observed-law anchors is speculation — drop it. This is the reasoning-mode analogue of the Domain agent's cite-or-omit rule. `confidence` is `"inferred"` by default; only `"stated"` when the derivation is mechanically airtight.

**Set `domain_role`** on each derived law to `"core"`, `"supporting"`, or `"platform"` — inherit it from the anchors' roles (each observed law in `domain_invariants` carries `domain_role`). If the anchors mix roles, use the role of the law's primary subject; prefer `"core"` whenever a core anchor is load-bearing in the derivation. This keeps the rendered output leading with core laws. Lead with core derived laws; in default depth ration supporting/platform derived laws the same way the Domain agent does (comprehensive depth lifts all caps).

## 3. `unenforced_invariants` — the gap list (UNGROUNDED — worth knowing, may be wrong)

The inverse question: *what laws should this product enforce, but nothing in the code does?* An enforced invariant is already safe (the code stops you). The dangerous laws are the ones everyone assumes hold but nothing checks — those are the latent bugs. Run the same taxonomy (conservation, value-bound, lifecycle, idempotency, tenant-isolation, append-only, referential) against each core entity and, where the domain clearly implies a law but you found NO enforcing guard / FSM edge / test / DB constraint, emit a gap.

```json
"unenforced_invariants": [
  {
    "id": "gap-001",
    "expected_law": "An issued charge record's total equals the sum of its line amounts.",
    "entity": "ChargeRecord",
    "category": "conservation",
    "why_expected": "Standard double-entry conservation; the product issues charge records customers are billed against.",
    "searched": ["app/billing/**/validate.ext", "app/billing/**/*_test.ext", "charge-record state machine"],
    "found_enforcement": "none",
    "risk": "A line-mutation path that skips total recompute drifts the charged amount from the line sum, undetected.",
    "confidence": "inferred"
  }
]
```

**Proof-of-absence discipline:** this section makes TWO fallible claims — *"this law should exist"* (a domain judgment) and *"nothing enforces it"* (proof of absence). To stay honest:
- `searched` is **REQUIRED and non-empty** — list the specific places you looked (validation code, FSM tables, test directories) so a human can falsify "nothing enforces it" in seconds. Cite the premises of your search, the same way derived laws cite their premises.
- Only emit a gap when the expected law is clearly implied by the product's domain AND your search genuinely found no enforcement. When unsure whether something enforces it, do NOT emit the gap — a false "you don't validate X!" when the product does is the failure mode.
- The whole section is `confidence: "inferred"` by construction. It is advisory: it will be rendered in a clearly-labeled "unverified" section and will NEVER become an enforcement rule.

## Depth

Default depth — derive the load-bearing laws and the highest-risk gaps only (soft caps: `derived_invariants` ~8, `unenforced_invariants` ~8). The comprehensive preamble lifts the caps. Never lower derivation/search rigor for coverage.

## Critical

- Everything you emit must be specific to THIS product and trace back to its observed laws or data models. Never generic programming advice.
- If the input has an empty `domain_invariants` array, you have nothing to reason from — emit empty `derived_invariants` and `unenforced_invariants`, and a minimal `product_model` only if `data_models`/`components` clearly support one. Empty is a correct answer; do NOT pad.

GROUNDING RULES apply (see below).
