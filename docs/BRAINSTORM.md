# Archie Strategic Brainstorm

> Generated March 2026 from multi-angle research: product positioning, market trends, and user friction audit.

---

## Why Users Aren't Excited — The Brutal Truth

Three independent research angles converged on the same core issues:

### 1. The Value Is Real But Invisible

Archie's output improves AI agent behavior — but the user never *sees* this improvement directly. They run analysis, get markdown, push it to repo... and then what? They have to *trust* that Claude Code will make better decisions. There's no before/after moment. No dopamine hit.

**Key data point:** An [ETH Zurich study (Feb 2026)](https://www.marktechpost.com/2026/02/25/new-eth-zurich-study-proves-your-ai-coding-agents-are-failing-because-your-agents-md-files-are-too-detailed/) found LLM-generated context files actually *reduce* task success by 3% on average and increase costs 20%+. However, the researchers specify that *non-inferable details* (architecture decisions, deployment patterns, custom conventions) ARE valuable. Generic descriptions of what the code does are actively harmful.

### 2. Setup Cost vs. Time-to-Value Is Inverted

- **Repomix**: `npx repomix` → output in 5 seconds, zero config
- **Archie**: Docker + Postgres + Redis + API key + 15-30 min setup → output in 2-5 min

The user pays upfront (setup) for deferred value (AI agents work better... eventually). Developer tools that win have *instant* time-to-value.

### 3. The Audience Problem

The person running Archie on their codebase **already understands their codebase**. They're looking at a mirror. The output is for *someone else* — a new team member, an AI agent, a future developer. But the person doing the work doesn't directly benefit.

### 4. Freshness Kills Long-Term Value

Code changes daily. Archie's output is a snapshot. The incremental mode only covers per-folder CLAUDE.md enrichment — the full 7-9 phase analysis always re-runs. No CI/CD integration, no webhooks, no auto-sync. Output goes from "useful" to "misleading" in weeks.

---

## The Market Opportunity Is Real — But Mispositioned

### What the market data says

| Signal | Data |
|--------|------|
| #1 developer pain with AI | Missing codebase context (65% cite this during refactoring) |
| AGENTS.md adoption | 60,000+ repos, supported by every major IDE |
| MCP adoption | 97M+ monthly SDK downloads, 6,400+ servers |
| Context engineering | Emerging as a recognized discipline (Martin Fowler, Anthropic) |
| Direct competitors doing what Archie does | **Zero.** Nobody does analysis → structured blueprint → multi-format output |
| Architect MCP compliance data | 80% pattern compliance with runtime tools vs 30-40% with docs alone |

**The gap is wide open.** No tool generates CLAUDE.md / AGENTS.md / Cursor rules from automated multi-phase analysis. Repomix concatenates files (no analysis). Greptile does code review. Augment indexes for retrieval. Sourcegraph does search. Nobody synthesizes architecture into a structured blueprint.

### Competitive Landscape

| Competitor | Approach | Gap vs. Archie |
|---|---|---|
| **Repomix** | Packs raw code into single file | No analysis or structure — just concatenation |
| **Greptile** ($30/dev/mo) | Graph-based code review | Focused on PR review, not persistent documentation |
| **Augment Code** | Live context engine (400K+ files) | Proprietary, enterprise-only, no exportable docs |
| **Sourcegraph Cody** ($19/user/mo) | RAG-based code search | Search tool, not a documentation generator |
| **Swimm** ($16-29/seat/mo) | Living documentation | Requires manual authoring; helps maintain, not generate |
| **Mintlify** ($300/mo Pro) | AI doc generation | API/code-level docs, not architectural understanding |
| **CodeSee** | Architecture visualization | Acquired by GitKraken (May 2024) — standalone may not be viable |
| **Architect MCP** | Runtime pattern enforcement | Enforces rules but doesn't analyze/generate them |

---

## Friction Points Audit

| Friction | Impact | Severity |
|----------|--------|----------|
| Setup complexity (Docker, Postgres, Redis, API key) | Hours of debugging if anything breaks | **High** |
| No transparent cost model (7-9 Claude API calls per analysis) | Uncertain bill; could be $1 or $10 per analysis | **High** |
| Incremental re-analysis doesn't cover phased analysis | Most cost savings don't apply; still pay for full pipeline | **Medium** |
| Outputs only useful if team adopts CLAUDE.md workflow | Depends on IDE adoption; not a team mandate | **Medium** |
| MCP tools require active IDE integration | Developers can ignore them; no enforcement | **Medium** |
| Freshness is manual, not automatic | No continuous sync; requires re-analyze-and-re-deliver | **Medium** |
| No hosted SaaS version — self-host only | Every user must run infrastructure | **High** |
| No cost dashboard or budget controls | Risk of surprise bills | **Low** |

### The "So What" Moment

After analysis, a developer gets:
1. **CLAUDE.md files** — pretty, but static unless they re-run
2. **MCP tools** — powerful, but only if they call them
3. **Cursor rules** — nice-to-have, but not enforced
4. **AGENTS.md** — aspirational guidance, not binding

But what they *don't* get:
- Automatic enforcement (code review bots, pre-commit hooks)
- Real-time feedback as they code (no IDE lint, no squiggles)
- Continuous freshness (no auto re-analysis on commits)
- Clear ROI (no metrics on whether the blueprint was followed)

---

## Three Strategic Directions

### Direction 1: "Zero-Friction CLI" — The Repomix Killer

**Philosophy:** Meet developers where they are. No web UI, no database, no Docker.

```bash
pip install archie-cli
archie analyze .                    # → generates .claude/, .cursor/, AGENTS.md
archie mcp serve                    # → starts MCP server for current repo
```

**What changes:**
- Strip the web UI, database, Redis requirement for the core use case
- Single dependency: Anthropic API key
- Output goes directly into the repo as committed files
- Optional `archie serve` for the web dashboard
- CLI handles incremental re-analysis via git hooks

**Why:** Repomix has massive adoption because it's `npx repomix`. But it does zero analysis — it's just concatenation. Archie's analysis pipeline produces genuinely better output. Package that in the same zero-friction format.

**Risk:** Loses the visual appeal. But developers don't live in web dashboards.

### Direction 2: "Architecture Linter in CI" — The ESLint for Architecture

**Philosophy:** Don't generate docs. Detect violations. Run on every PR.

```yaml
# .github/workflows/archie.yml
- uses: archie/check@v1
  with:
    anthropic-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

PR comment:
> "This PR adds a direct database call in `api/routes/users.py` — your architecture uses the repository pattern. Consider using `UserRepository` instead. See `components.data_access`."

**What changes:**
- Blueprint becomes a **contract**, not a document
- Analysis runs once to establish baseline, then `archie check` runs per-PR
- Freshness problem solved: blueprint is validated against every change
- Clear value: prevents architectural drift automatically
- Measurable ROI: "blocked X violations this month"

**Why:** The Architect MCP server reports 80% pattern compliance vs 30-40% with docs. Runtime enforcement beats static docs every time. And CI/CD is where teams already enforce quality.

**Risk:** Requires solid baseline blueprint. False positives would kill adoption.

### Direction 3: "Context Compiler for AI Agents" — Double Down on MCP

**Philosophy:** The documentation is a side effect. The real product is the MCP tools.

**What changes:**
- Lead with the MCP pitch: "Your AI assistant knows your architecture in real-time"
- The hero demo: Claude Code asks `where_to_put("new payment service")` and gets the right answer
- Reduce from 10 MCP tools to 3-4 high-signal ones (token budget matters — 7 MCP servers eat 33% of context)
- Add enforcement: `check_compliance` tool that blocks bad placements
- Publish as an MCP server in the registry (5,800+ servers, discoverable by all IDEs)

**Why:** MCP is the winning standard. 97M+ monthly SDK downloads. Every IDE supports it. Being the "architecture-aware MCP server" is a unique, defensible position.

**Risk:** MCP ecosystem is noisy. Standing out among 6,400 servers requires exceptional UX.

---

## Recommended Roadmap: 1 + 3 Hybrid, Then 2

### Phase 1 (Weeks): CLI + MCP — Zero to Value in 60 Seconds

```bash
pip install archie
archie init .                       # Analyzes repo, generates blueprint + context files
archie mcp                          # Starts MCP server, auto-detected by Claude Code/Cursor
```

- No database, no Docker, no web UI
- Single requirement: `ANTHROPIC_API_KEY`
- Generates: `.claude/`, `.cursor/`, `AGENTS.md`, `.archie/blueprint.json`
- MCP server reads from `.archie/blueprint.json` (no database needed)
- Git hook: `archie refresh` on pre-commit (lightweight, only re-enriches changed folders)

### Phase 2 (Months): CI Integration — Architecture Enforcement

```yaml
- uses: archie/check@v1  # Runs on every PR
```

- Compares PR diff against `.archie/blueprint.json`
- Comments on architectural violations
- Dashboard shows drift metrics over time
- This is where the SaaS/monetization happens

### Phase 3 (Later): Web Dashboard — Optional Power Tool

- Keep the existing web UI as `archie dashboard`
- For teams that want visual exploration, history, comparisons
- Not the entry point — the CLI is

---

## What Would Make Users Enthusiastic (Ranked)

1. **30-second time-to-value**: `pip install archie && archie init .` → files in repo, done
2. **Visible before/after**: "Without Archie, Claude put the handler in the wrong layer. With Archie's MCP, it asked `where_to_put` and got it right."
3. **Automatic freshness**: Git hook or CI, not manual re-runs
4. **Architecture violation blocking**: PR comments that prevent drift
5. **Cost transparency**: Show token usage and estimated cost before/after analysis
6. **Concise, non-obvious output**: The ETH Zurich research says keep context files under 300 lines and focus on what AI *can't* infer from code alone (decisions, conventions, deployment patterns)

---

## The One-Line Pitch Reframe

**Current:** "AI-powered architecture documentation generator"

**Proposed:** "Your AI writes code. Archie makes sure it follows your architecture."

The documentation is a side effect. The enforcement is the product.

---

## Key Market Data Points

- **Developer pain #1**: Missing codebase context — 65% cite this during refactoring; 26% of all improvement requests ([RedMonk 2025](https://redmonk.com/kholterhoff/2025/12/22/10-things-developers-want-from-their-agentic-ides-in-2025/))
- **METR Study**: AI tools made experienced devs [19% slower](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/), despite devs believing they were 24% faster
- **Stack Overflow 2025**: Trust in AI accuracy fell from 40% to 29%; favorability dropped from 72% to 60%
- **MCP adoption**: [97M+ monthly SDK downloads](https://mcpmanager.ai/blog/mcp-adoption-statistics/), 6,400+ servers, adopted by OpenAI, Google, Microsoft
- **MCP token concern**: 7 active MCP servers consume ~67K tokens ([33.7% of 200k context](https://zuplo.com/mcp-report))
- **AGENTS.md**: [60,000+ repos](https://layer5.io/blog/ai/agentsmd-one-file-to-guide-them-all/), supported by Claude Code, Cursor, Copilot, Gemini, Windsurf, Aider, Zed, Warp
- **ETH Zurich**: LLM-generated context files [reduce success by 3%](https://arxiv.org/html/2602.11988v1) — but non-inferable details (decisions, conventions) are valuable
- **Architecture enforcement**: [80% compliance](https://dev.to/vuong_ngo/ai-keeps-breaking-your-architectural-patterns-documentation-wont-fix-it-4dgj) with runtime MCP tools vs 30-40% with docs alone
- **Context engineering**: Emerging discipline — [Martin Fowler](https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html), Anthropic, multiple research papers
- **CodeSee acquisition**: [Acquired by GitKraken](https://www.schneider.im/gitkraken-acquired-codesee/) — standalone architecture viz may not be viable as independent business
- **Pricing sweet spot**: [$20-30/user/month](https://www.heavybit.com/library/article/pricing-developer-tools) for developer tools; >$50 sees significant drop-off
- **Freemium conversion**: [2-5% typical](https://www.kinde.com/learn/billing/conversions/freemium-to-premium-converting-free-ai-tool-users-with-smart-billing-triggers/), 7-10% best-in-class

---

## Suggested Pricing Model (If/When Monetizing)

| Tier | Price | Includes |
|------|-------|----------|
| Free | $0 | CLI analysis (2 repos), MCP server, all output formats |
| Pro | $25/month | Unlimited repos, CI integration, incremental analysis |
| Team | $20/user/month | Dashboard, drift metrics, team-wide rules, SSO |
| Enterprise | Custom | Self-hosted, SOC 2, dedicated support |

The MCP server and CLI should be the free hook that drives adoption. Monetize on CI enforcement, team features, and dashboards.
