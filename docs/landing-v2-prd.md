# Archie Landing Page v2 — PRD

**Status:** Draft · **Branch:** `feature/landing-v2` · **Owner:** Gabor

---

## 1. Overview

### Goal
Replace the current 8-section landing page with a focused, 5-frame narrative that lands the Archie thesis in under 60 seconds of scrolling and converts the visitor to running `npx @bitraptors/archie .`.

### Audience
**Primary:** Individual developers and small teams using Claude Code (or equivalent agents) who feel the codebase-erosion problem firsthand.
**Secondary:** Engineering leaders evaluating tooling for their teams.

The voice is built for the primary — terminal screenshots, command-line specifics, agent-native vocabulary ("velocity," "drift") rather than enterprise framing ("Time to Market," "Uptime SLA").

### Success Metrics
- **Scroll-through rate** to Frame 5 ≥ 40% (vs. v1 baseline once measured)
- **CTA clickthrough** to GitHub ≥ 8%
- **`npx` install events** within 24h of visit (tracked separately)
- **Time on page** ≥ 90s median

### Non-Goals
- Enterprise sales motion (no "Request a Demo" form, no logo wall)
- Long-form documentation (link out to repo for that)
- Pricing / tiers (Archie is OSS — keep this clean)
- Multi-page IA (single-page scroll, no nav tabs)

---

## 2. Background

### Why v2
v1 (preserved at `v1/landing/`) was a strong first cut but sprawls across 8 sections that compete for attention:
- Hero, Problem, Solution (9-phase pipeline), Native in Claude Code, Per-Folder, Showcase, What Gets Generated + Numbers, Final CTA.
- The thesis is split across "Solution" and "Per-Folder" and "What Gets Generated" — no single load-bearing idea.
- The differentiator (semantic understanding, multi-wave AI, severity-gated hooks) is buried under feature lists.

v2 reorganizes around **one thesis: Archie builds semantic understanding of your codebase**, with four pillars and four outcomes flowing from it.

### What v1 Did Well (carries over)
- Brutalist + neon + deep-space aesthetic — distinctive, memorable
- Scroll-scrubbed animations and parallax depth
- Live file tree showcase with modal expansion (Frame 4 hero)
- Sticky scroll progress bar + raptor feedback easter egg
- Section-numbered labels (`01. THE SOLUTION`)
- Vertical-text background watermarks

### What v1 Missed (v2 must fix)
- No clear thesis sentence
- "How it works under the hood" is reduced to a single screenshot — the multi-wave AI architecture and severity-class enforcement model aren't surfaced
- Outcomes are scattered — no Frame 5 payoff
- Workflow steps live in the final CTA section, not in their own frame
- The "decision preservation" and "compound learning" angles are absent

---

## 3. Design System

**Source of truth:** [`landing/DESIGN.md`](../landing/DESIGN.md). All color tokens, typography, style language, animation principles, AI slop guard, and component inventory live there. Update DESIGN.md when design decisions change — don't bury new tokens in this PRD or in component code.

**Per-frame accent assignments (v2-specific):**
- Frame 1 — amber-flame for stats, neon for headline glow
- Frame 2 — neon for hero pillar, sky-blue/amber-flame/princeton-orange for supporting
- Frame 3 — sky-blue for build phase, princeton-orange for enforce
- Frame 4 — blue-green for cards, sky-blue radial-gradient bg
- Frame 5 — neon for hero outcome, sky-blue/amber-flame/princeton-orange for supporting

**Vertical text watermarks per frame:** "EROSION" (Frame 1), "UNDERSTANDING" (Frame 2), "PIPELINE" (Frame 3), "OUTPUT" (Frame 4), "OUTCOMES" (Frame 5).

<!-- Section 3 used to contain a full design system spec. It now lives in landing/DESIGN.md. The old subsections are preserved below for reference during the v2 build, but DESIGN.md is canonical. -->

### Color Tokens (from `app/globals.css`)
| Token | Hex | Use |
|---|---|---|
| `--color-neon` | `#39ff14` | Primary accent · CTAs · borders · emphasis |
| `--color-sky-blue` | `#8ecae6` | Secondary accent · annotations · code highlights |
| `--color-blue-green` | `#219ebc` | Tertiary accent · pipeline diagrams |
| `--color-deep-space-blue` | `#023047` | Primary background |
| `--color-deep-space-blue-100` | `#00090e` | Deeper background (alternating sections) |
| `--color-amber-flame` | `#ffb703` | Warning · highlight · stats |
| `--color-princeton-orange` | `#fb8500` | Critical CTA · severity escalation |
| `--foreground` | `#e8f4fa` | Body text |

### Typography
- **Headings:** Inter (`--font-sans`) — black weight (900), uppercase, tight tracking
- **Body / code:** Space Mono (`--font-mono`) — used as default `body` font for the brutalist tech feel
- **Scale:** Hero `text-4xl md:text-8xl lg:text-9xl`, Section H2 `text-3xl md:text-7xl`, Body `text-xl`

### Style Language
- **Brutalist borders:** `2px solid neon` + `8px 8px 0px 0px` offset shadow, transitions to `4px 4px` on hover with `translate(4px, 4px)` (interactive press feel)
- **Glassy cards:** `backdrop-blur-xl` over `rgba(2, 48, 71, 0.6)` for premium depth on dark backgrounds
- **Neon glow:** `text-shadow: 0 0 10px rgba(57, 255, 20, 0.5)` on key text
- **Mix-blend-difference:** hero heading punches through shader background
- **Per-section accent color:** each frame leans on one secondary color (Frame 1 amber-flame, Frame 2 neon, Frame 3 sky-blue, Frame 4 blue-green, Frame 5 princeton-orange)
- **Vertical text watermarks:** `writingMode: vertical-rl` background labels at `opacity: 0.02-0.05`, e.g., "MEMORY", "ENFORCE", "OUTPUT"

### Animation Principles
- **Scroll-scrubbed headings:** side-to-side translation as user scrolls (GSAP `ScrollTrigger`, `scrub: 1`, `start: "top center"`, `end: "bottom top"`)
- **Parallax images:** containers `overflow-hidden`, inner `25%` Y-translation on scroll
- **Fade-up reveals:** `from { y: 100, opacity: 0 }` triggered at `top 85%`, `duration: 1.5s`, `ease: power4.out`, `toggleActions: "play none none reverse"`
- **Spring physics on UI:** Framer Motion springs for the raptor easter egg and modal transitions (`stiffness: 260, damping: 20`)
- **Smooth scroll:** Lenis (already wired in `SmoothScroll.tsx`)
- **Card hover transition:** `0.2s ease` on shadow + transform (matches v1 brutalist hover)
- **Stagger:** when 3+ siblings animate in (e.g., 3 supporting pillars in Frame 2), stagger by 100ms for visual rhythm
- **Animation budget:** at most 3 simultaneous animations per scroll viewport — no animation walls

### AI Slop Guard

These patterns are **forbidden** in v2 components. Designer/dev must check work against this list before committing:

1. ❌ Symmetric 4-card grids (use hero + 3 supporting instead — see Frame 2/5)
2. ❌ Icons inside colored circles (use flat icons in accent color)
3. ❌ Centered text on every section (left-align by default; center is a deliberate choice)
4. ❌ Bubbly border-radius (zero radius = brutalist; selective use only on the modal close button per v1)
5. ❌ Decorative blobs, floating circles, wavy SVG dividers (use radial gradients + dot grids per v1 vocabulary)
6. ❌ Emoji as design elements (footer ❤️ is the only exception, inherited from v1)
7. ❌ Generic hero copy ("Welcome to Archie", "Your all-in-one solution")
8. ❌ Cookie-cutter section rhythm (hero → 3-features → testimonials → CTA — your structure is intentionally different)
9. ❌ Purple/violet/indigo gradients (palette is locked to deep-space-blue + neon green + sky-blue + amber-flame + princeton-orange)
10. ❌ Stock imagery, icon-in-colored-circle, "happy people" photos

### Component Inventory (reuse from v1)
- `ShaderBackground` — animated hero background
- `SmoothScroll` — Lenis wrapper
- `MarkdownRenderer` — for Frame 4 file content
- `FileTree` — for Frame 4 file browser
- `example-files.ts` + `example-data.json` — file content for Frame 4 (will need refresh)

---

## 4. Frame Specifications

Five frames, full-bleed sections, vertical scroll. Each frame must work as a single screen on desktop (no required scroll within a frame to grasp it) but can have supporting detail below the fold.

### Frame 1 — The Hook (Problem)

**Section background:** `bg-deep-space-blue` with `ShaderBackground` overlay + neon dot grid (`radial-gradient(#39ff14 1px, transparent 1px)` 40px tile, opacity 0.2).

**Product badge (above headline):** Small mono-font tag — `• ARCHIE · architecture analysis for AI agents` — neon accent dot, sky-blue text, `text-xs` uppercase tracking-widest. Answers the 5-second "what is this?" test without diluting the pain-first hook.

**Headline (mix-blend-difference, scroll-scrubbed):**
> Agent-built codebases erode faster than agents can patch them.

**Subhead (left-bordered, glassy):**
> Without semantic understanding, every PR drifts a little further from the architecture you started with — and agents have no way to know.

**Primary visual — decay curve spec:**
- **Format:** inline SVG component (`components/DecayCurve.tsx`)
- **Type:** line chart, 600x300 viewport, scaled responsively
- **Axes:** X = "Week 1" → "Week 12" (mono font, sky-blue, `text-xs` uppercase). Y = "Agent velocity" (rotated 90°, mono font, sky-blue)
- **Curve:** starts top-left at week 1 (high), drops sharply between weeks 4-8, bottoms out by week 12. Stroke: 3px, neon green, with `text-glow-neon` shadow
- **Annotation points:** small neon dots at week 1, 6, 12 with mono-font labels: "Week 1: Fresh repo", "Week 6: First drift", "Week 12: Compounding chaos"
- **Animation:** `stroke-dasharray` draw-in over 1.5s on scroll into view (uses `Framer Motion`). Static (fully drawn) on `prefers-reduced-motion`
- **Anchored stat card overlaid bottom-right:** brutalist-bordered, glassy bg, *"After 50 AI-assisted PRs, you have 50 different interpretations of your architecture."* — sky-blue text, `text-base` mono

**Supporting evidence (below-fold, parallax):** Reuse the v1 stat block:
- `65%` say AI misses context during refactoring
- `44%` blame context gaps for quality degradation
- Source: State of AI Code Quality, 2025

**CTA:** Soft scroll cue (no button) — "How Archie fixes this ↓"

**Accent color:** `amber-flame` for stats, `neon` for headline.

---

### Frame 2 — The Thesis

**Section background:** `bg-deep-space-blue` with vertical "UNDERSTANDING" watermark (right side, opacity 0.03).

**Section label:** `01. THE THESIS` (neon on neon/10 chip, left-bordered).

**Headline:**
> Archie builds semantic understanding of your codebase.

**Subhead:**
> Curated knowledge, delivered exactly where and when agents need it.

**Four pillars — asymmetric hierarchy.** One hero pillar (full-width or 2-col span) anchors the section, three supporting pillars below in a 3-column row. Breaks 2x2 symmetry, leads with the most differentiated capability. **Anti-pattern flagged in design review:** symmetric 4-card grids read as "here are 4 features," compete for attention, and trip AI-slop pattern #2 (3-column feature grid).

**Layout (desktop):**
```
┌──────────────────────────────────────────────┐
│  AT EDIT TIME (HERO — 2x scale, neon green)  │
│  Hooks reject bad edits in real-time,        │
│  before they land. Not at PR review.         │
└──────────────────────────────────────────────┘
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ AT PLANNING  │ │ IN CONTEXT   │ │ OVER TIME    │
└──────────────┘ └──────────────┘ └──────────────┘
```

**Layout (mobile):** Hero card full-width, three supporting cards stack vertically below.

| Role | Pillar | Description | Icon | Accent |
|---|---|---|---|---|
| **HERO** | **At edit time** | Hooks reject bad edits in real-time, before they land | `Shield` | **neon** |
| Supporting | At planning | Agents read the blueprint and decisions before writing a line | `BookOpen` | sky-blue |
| Supporting | In context | Per-folder `CLAUDE.md` scopes understanding to the file at hand | `FolderTree` | amber-flame |
| Supporting | Over time | Every scan deepens the model; drift becomes new rules | `TrendingUp` | princeton-orange |

**Why edit-time as hero:** real-time enforcement is Archie's most differentiated capability. No competitor does this. Leading with it serves the visitor, not the brand.

**Card visual spec:**
- **Background:** `bg-deep-space-blue-100` (deeper than section bg) with brutalist border (2px solid, accent color), 8px x 8px hard offset shadow
- **Icon:** flat Lucide icon (`Shield`, `BookOpen`, `FolderTree`, `TrendingUp`), 32px supporting / 48px hero, accent color, top-left, no circle/box behind it (avoids AI slop pattern #3)
- **Label:** Inter Black uppercase, `text-2xl` supporting / `text-4xl` hero, accent color
- **Description:** Space Mono, `text-sm` supporting / `text-base` hero, gray-300, max 2 lines
- **Padding:** `p-8` supporting / `p-12` hero
- **Hover:** shadow shifts 8px→4px, card translates `(4px, 4px)` (existing v1 brutalist pattern), icon rotates 5°. Hero card hover scales shadow shift to 12px→6px and `(6px, 6px)` translation to emphasize weight. Transition: `0.2s ease`.

**Below the four pillars:** A one-line transition to Frame 3 — *"Here's how Archie actually does it."*

---

### Frame 3 — Under the Hood

**Section background:** `bg-deep-space-blue-100` with subtle blue-green gradient. Vertical "PIPELINE" watermark.

**Section label:** `02. UNDER THE HOOD`.

**Headline:**
> Multi-wave AI analysis. Semantic enforcement.

**Subhead:**
> Archie runs the same analysis a senior architect would — then embeds the conclusions where agents work.

**Layout:** Two-column on desktop, stacked on mobile.

**Mobile reading order:** Build phase first, then enforce phase. Chronological — visitors must understand what Archie analyzes before "how it's enforced" makes sense.

#### Left column — Build phase (`/archie-deep-scan`)

A vertical pipeline diagram (custom SVG or styled divs) showing:

1. **Deterministic scan** — file tree, frameworks, layer detection
2. **Wave 1 (parallel Sonnet agents)**, four cards in a row inside this step:
   - Structure → components, layers, placement
   - Patterns → communication, design patterns
   - Technology → stack, deployment, dev rules
   - UI Layer *(if frontend)* → state, routing
3. **Wave 2 (Opus reasoning)** — decision chains, trade-offs, pitfalls with causal links
4. **Intent layer** — per-folder `CLAUDE.md` via bottom-up DAG

Animation: arrows draw between steps as user scrolls. Wave 1 cards fan out in parallel.

Footer label: *"One-time, ~15 min."*

#### Right column — Enforce phase (every agent edit)

A "rule card" mockup showing the inline structure:

```
┌─ rule: domain_layer_boundary ──────────────┐
│ severity_class: decision_violation         │
│                                            │
│ DESCRIPTION                                │
│ Domain layer must not import from          │
│ infrastructure or API layers.              │
│                                            │
│ WHY                                        │
│ Forced by: clean architecture decision...  │
│ Enables: independent testability...        │
│                                            │
│ EXAMPLE                                    │
│ ✓ from domain.entities import User         │
│ ✗ from infrastructure.db import Session    │
└────────────────────────────────────────────┘
```

Below the rule card, a severity-gates legend:

| Severity | Action | Color |
|---|---|---|
| `decision_violation` · `pitfall_triggered` · `mechanical_violation` | **Blocks** (exit 2) | princeton-orange |
| `tradeoff_undermined` | **Warns** prominently | amber-flame |
| `pattern_divergence` | **Informs** quietly | sky-blue |

Footer label: *"Fires on every edit."*

#### Below both columns — Maintenance loop

Single horizontal strip:
> **`/archie-scan`** (1-3 min, run often) — Senior-architect pass on the diff. New findings become new rules. The model sharpens with every run.

**Accent color:** `sky-blue` for build phase, `princeton-orange` for enforce.

---

### Frame 4 — The Receipts (Output)

**Section background:** `bg-black` with sky-blue radial gradient top-right. This is the showcase frame — let the artifacts breathe.

**Section label:** `03. RECEIPTS`.

**Headline:**
> This is what semantic understanding looks like.

**Subhead:**
> No marketing screenshots. Real output from real codebases.

**Three artifacts** in a horizontal scrolling carousel on mobile, three-column layout on desktop. Each artifact lives in a brutalist-bordered terminal-style card.

**Terminal card visual spec:**
- **Background:** `bg-black` (#000), brutalist border (2px solid, accent color varies by artifact), 8px x 8px hard offset shadow
- **Header bar:** thin row at top with file path in mono, sky-blue, `text-xs` uppercase (e.g., `> .archie/rules.json`)
- **Body font:** Space Mono, 13px (`text-[13px]`), `leading-relaxed`
- **Color coding:** primary text neon green (`#39ff14`), annotations sky-blue, errors/violations princeton-orange, warnings amber-flame
- **Card sizing:** Hook-rejection card spans 2 columns on desktop (the hero); per-folder + scan-report cards span 1 each
- **Hover:** shadow shift to 4px (matches pillar pattern); cursor signals expandability over the body
- **Expand affordance:** `[Maximize2]` icon (Lucide) in bottom-right, opacity 0 → 1 on card hover, opens the modal viewer (existing v1 component)

**Reading order on all viewports:** Hook rejection (1) → Per-folder `CLAUDE.md` (2) → `scan_report.md` (3). Lead with the most visceral artifact; the other two reinforce. Mobile carousel starts on Artifact 1 (hook rejection) by default.

#### Artifact 1 — Hook rejecting an edit (hero shot)
Terminal-style block with realistic agent output:
```
> Edit blocked by Archie hook:
  decision_violation: domain_layer_boundary

> WHY: The domain layer must remain
  independent of infrastructure.
  Importing Session here would couple
  business logic to the database driver.

> EXAMPLE:
  ✓ Define a UserRepository interface
    in domain/interfaces/
  ✗ Import infrastructure.db.Session
    directly

> Fix the import or update the rule
  in .archie/rules.json
```
**Most visceral artifact — make this the largest of the three.**

#### Artifact 2 — Per-folder CLAUDE.md excerpt
Real `CLAUDE.md` content from a deep folder (e.g., `backend/src/api/routes/`). Shows:
- File-level purpose statement
- Conventions specific to that folder
- 1-2 references to parent decisions

Use the existing `MarkdownRenderer` component from v1.

#### Artifact 3 — `scan_report.md` ranked findings
Compact list of ranked drift findings with severity badges. Shows:
- Finding title
- Severity class (color-coded)
- File path
- Brief reasoning
- Source decision link

**Interaction:** Each card has a "See the full file" expander that opens the existing modal viewer (reuse from v1's showcase modal). The `FileTree` component drives the modal browser.

**File set update:** `example-files.ts` needs new content reflecting v2.5+ output (with `decision_chain`, `severity_class`, `WHY`/`EXAMPLE` blocks). Pull from a real Archie run on a public repo (BabyWeather.Android or similar).

---

### Frame 5 — The Outcomes (Value)

**Section background:** `bg-deep-space-blue` with thick `border-y-[8px] border-neon` framing. Vertical "OUTCOMES" watermark.

**Section label:** `04. OUTCOMES`.

**Headline (large, scroll-scrubbed):**
> Ship faster. Ship safer. Forever.

**Subhead:**
> Semantic understanding compounds — the longer Archie runs, the sharper it gets.

**Four outcomes — asymmetric hierarchy (mirrors Frame 2).** Hero outcome anchors the section; three supporting outcomes below in a row. Frame 2's hero is the most-different *capability* (edit-time enforcement); Frame 5's hero is the most-different *long-term value* (compound learning). Same shape, different content — visual rhythm that reinforces Archie's signature without feeling templated.

**Layout (desktop):**
```
┌──────────────────────────────────────────────┐
│  YOUR CODEBASE LEARNS (HERO — neon)          │
│  Incidents become rules. Agents inherit      │
│  the scar tissue.                            │
└──────────────────────────────────────────────┘
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ VELOCITY     │ │ NO DRIFT     │ │ DECISIONS    │
│ STAYS HIGH   │ │ TO PROD      │ │ PRESERVED    │
└──────────────┘ └──────────────┘ └──────────────┘
```

**Layout (mobile):** Hero card full-width, three supporting cards stack vertically below.

| Role | Outcome | Description | Accent |
|---|---|---|---|
| **HERO** | **Your codebase learns** | Incidents and drift become rules; agents inherit the scar tissue | **neon** |
| Supporting | Velocity stays high | Agents start every task with context, not from scratch | sky-blue |
| Supporting | No drift to prod | Hooks catch architectural mistakes before commit | amber-flame |
| Supporting | Decisions preserved | The *why* survives every refactor | princeton-orange |

**Why "your codebase learns" as hero:** compound learning is the long-term moat. Other tools shrink as your codebase grows; Archie sharpens. This is the strongest closing argument before CTA.

**Card visual spec:** identical structure to Frame 2 pillar cards (Lucide icons flat in accent color, 32px supporting / 48px hero, brutalist border + offset shadow, hover behavior shared). Outcome icons: `TrendingUp` (hero), `Zap` (velocity), `Shield` (no drift), `BookOpen` (decisions preserved).

**Final CTA block** (centered, slightly rotated for v1's signature look):
- Headline: *"Stop watching your codebase erode."*
- Sub: *"Three minutes to install. Compounding returns from day one."*
- Primary CTA: `npx @bitraptors/archie .` (mono font, brutalist border, neon `[Copy]` button — see section 6 for state spec)
- Secondary CTA: "View on GitHub" text link with `★ N` star badge (mono font, build-time fetch, hidden if N < 50)

**Footer:** Reuse v1 footer (BitRaptors attribution, Documentation, GitHub, Privacy).

---

## 5. Cross-Frame Elements

### Sticky Scroll Progress Bar
Reuse from v1 — `motion.div` at `fixed top-0` with `scaleX: scaleProgress`, neon color. Helps the visitor sense the deck length.

### Sticky Feedback Badge + Raptor Easter Egg
Reuse from v1 — `fixed bottom-6 right-6`, raptor SVG springs up on CTA hover. This is a brand asset; preserve it.

### Section Transitions
- Each frame separated by a thick neon border (`border-y-4` or `border-t-8`)
- Background colors alternate (deep-space-blue → deep-space-blue-100 → black → deep-space-blue) to give scroll-rhythm

### Section Numbering
Continue v1's `01. THE THESIS` style — small neon chip, uppercase, tracking-widest, left-bordered.

### Emotional Storyboard

The 5-frame deck is a designed emotional arc. Each frame has a target feeling and the design moves that support it:

| Frame | User does | User feels | What in the design supports it |
|---|---|---|---|
| **1 — Hook** | Lands on page, reads headline, sees decay curve animate | **Recognition + discomfort.** "Yes, this is happening to my codebase." | Pain-first headline; mix-blend-difference makes it punch through; decay curve animates downward; stat block with cited research validates the feeling is shared |
| **2 — Thesis** | Scrolls past curve, reads thesis headline, scans 4 pillars | **Relief + clarity.** "OK, there's an answer — and it's specific, not vaporware." | Hero pillar (At edit time) anchors with neon; subhead promises curated knowledge; four labeled mechanisms make the abstract concrete |
| **3 — Mechanism** | Reads pipeline + rule card, sees severity gates | **Confidence + technical respect.** "This was built by people who know what they're doing." | Multi-wave AI breakdown shows real architecture; severity gates show enforcement nuance (not just block/allow); `/archie-scan` maintenance loop shows it's alive |
| **4 — Receipts** | Reads three real artifacts, opens modal on hook rejection | **Trust + visceral payoff.** "This is real output. I can see it working." | Hook rejection in terminal aesthetic feels native; per-folder CLAUDE.md shows depth; modal reveals full content for skeptics |
| **5 — Outcomes** | Reads "Ship faster. Ship safer. Forever." + hero outcome, copies command | **Motivation + resolve.** "I want this. I'm installing now." | Hero outcome (compound learning) is the strongest closing argument; CTA is the literal install command, not a generic button |

**Design implications:** every animation, color choice, and typography decision should support the target feeling for that frame. If something feels "off" during implementation, check this column before tweaking.

**Time-horizon design:**
- **5 seconds** (visceral): product badge + pain headline + decay curve all readable above the fold. Visitor knows the product name, the problem, and that the page is technical.
- **5 minutes** (behavioral): visitor has scrolled to Frame 5, has the install command in muscle memory, knows what `/archie-deep-scan` is.
- **5 years** (reflective): brutalist + neon distinctive enough to remember; deep-space-blue + green palette is the brand signature.

---

## 6. Interaction States

Every interactive element has a defined state. Defaults below; override only when the brand voice demands it.

### Interaction state matrix

| Element | Idle | Hover | Active/Pressed | Loading | Empty | Error |
|---|---|---|---|---|---|---|
| **Pillar / outcome cards** | brutalist border + 8px offset shadow | shadow shifts to 4px, card translates 4px,4px (existing v1 pattern); icon rotates 5° | shadow collapses to 0, card fully translates 8px,8px | n/a | n/a | n/a |
| **Frame 1 scroll cue** | "How Archie fixes this ↓" with bouncing arrow | arrow stops bouncing, color flips to neon | n/a | n/a | n/a | n/a |
| **CTA: `npx @bitraptors/archie .`** | brutalist-bordered command in mono font + `[Copy]` button | button background fills neon, command shows full neon glow | label swaps to `[✓ Copied]` for 2s + one-time neon flash on command bg, then reverts | n/a (sync) | n/a | toast: "Copy failed — select and ⌘C" (3s, dismissable) |
| **CTA: GitHub link (Frame 5 secondary)** | neon underline | underline thickens, arrow icon translates +2px | brief opacity dip on click | n/a | n/a | n/a |
| **Modal: "See the full file"** | trigger button visible on artifact card hover | button fills neon | modal opens with spring animation (existing pattern) | spinner in modal body for first 200ms while content mounts | "File not found" with `Folder` icon + "Try another file" link (warmth + primary action) | "Couldn't load file" + retry button + GitHub link as fallback |
| **File tree (modal)** | items visible, indented | item highlights neon | active item gets neon left border (existing v1 pattern) | skeleton rows for first paint | "No files generated yet — run /archie-deep-scan" with link to docs | "File list unavailable" with reload button |
| **Hero shader background** | animated, opacity 1 | n/a | n/a | static gradient placeholder while shader compiles | n/a | static gradient (no shader) on WebGL failure |
| **Decay curve (Frame 1)** | static at scroll-start, animates draw-in on scroll into view | n/a | n/a | n/a | n/a | static SVG fallback (no animation) on JS error |
| **Pipeline diagram (Frame 3)** | static, animates connector arrows on scroll into view | step cards lift on hover (brutalist pattern) | n/a | n/a | n/a | static SVG fallback on JS error |
| **Scroll progress bar** | neon bar at top, scaleX bound to scroll | n/a | n/a | n/a | n/a | n/a |
| **Raptor easter egg** | hidden | springs up when CTA hovered (existing v1) | n/a | n/a | n/a | n/a |

### `prefers-reduced-motion` policy

When the user's OS signals reduced motion, the page MUST:

- **Disable:** scroll-scrubbed heading animations (the side-to-side translation), parallax image movement, decay curve draw-in animation, pipeline arrow draw-in animation, raptor spring-up
- **Keep:** fade-up reveals (mild, non-vestibular), hover effects on cards/buttons, scroll progress bar (low motion, communicates position), shader background (ambient, doesn't track scroll)
- **Replace:** scroll-scrubbed headings render at their final position; decay curve and pipeline diagram render fully drawn on first paint

Implementation: gate GSAP `ScrollTrigger` registrations in `useEffect` behind `window.matchMedia('(prefers-reduced-motion: reduce)').matches`. Re-evaluate on media query change.

### Empty-state warmth principle

Empty states are features. Each empty state has:
1. **Visual:** an icon (not just text) — `Folder`, `Search`, `FileText` from Lucide
2. **Copy:** what's not here + why
3. **Primary action:** a link or button forward (run a command, view docs, retry)

"No files found." is **not** a design. "No CLAUDE.md generated yet — run `/archie-deep-scan` to populate. [View docs →]" is.

## 7. Technical Requirements

### Stack (no changes from v1)
- Next.js 15 (App Router, RSC where possible)
- React 19
- Tailwind v4 (`@theme` block in `globals.css`)
- Framer Motion 11+ (animations)
- GSAP + ScrollTrigger (scroll-scrubbed animations)
- Lenis (smooth scroll)
- Lucide React (icons)

### Performance Budgets
- LCP < 2.5s on a 4G connection
- Total JS bundle < 250KB gzipped (excluding fonts)
- No CLS issues from late-loading shader background
- Hero image / shader: use CSS-only effects where possible to avoid blocking

### Accessibility (concrete commitments)

**Heading hierarchy:**
- Single `<h1>` (Frame 1 hero only)
- `<h2>` for each frame's section headline
- `<h3>` for sub-sections within frames (e.g., "Build phase", "Enforce phase" in Frame 3)

**Color contrast:**
- **Body text:** gray-300 (#D1D5DB) on all dark backgrounds (deep-space-blue, deep-space-blue-100, black) → 8:1+ contrast, AAA. **Globally tighter than v1's gray-400.**
- Section labels: sky-blue or accent color on deep-space-blue → audit each combo, target AA minimum
- Code blocks in terminal cards: neon green on black → 11:1+, AAA
- Error/warning text: princeton-orange or amber-flame on dark → audit and adjust if borderline

**Keyboard navigation:**
- Tab order follows DOM order top-to-bottom (no `tabindex` overrides)
- Focus rings: 2px solid neon outline + 2px offset (overrides browser default), visible on all interactive elements
- Modal: traps focus, ESC closes, restore focus to trigger button on close
- File tree: arrow keys navigate, Enter selects, ESC dismisses
- Copy CTA: Enter or Space triggers copy
- Skip link: hidden until focused, "Skip to main content" jumps past hero

**ARIA landmarks:**
- `<header>` for hero (Frame 1)
- `<main>` wraps Frames 2-5
- Each frame is `<section aria-labelledby="frame-N-headline">` with the headline carrying the matching `id`
- Modal: `role="dialog" aria-modal="true" aria-labelledby="..."`
- Footer: `<footer>`

**Touch targets:** minimum 44px × 44px for all interactive elements on mobile/tablet (matches Apple HIG). Pillar cards inherently exceed this; copy CTA button explicitly sized.

**Animation a11y:** see "`prefers-reduced-motion` policy" in section 6 (Interaction States).

**Image alt text:** every `<img>` has descriptive alt or `alt=""` for decorative. Audit v1's `pipeline.png` and others before reuse.

### Responsive Breakpoints

**Tailwind defaults used as breakpoints:**
- `sm`: 640px
- `md`: 768px (mobile / tablet boundary for layout shifts)
- `lg`: 1024px (tablet / desktop boundary)
- `xl`: 1280px
- `2xl`: 1536px (max content cap at `max-w-7xl`)

**Mobile (< 768px) — designed, not defaulted:**
- **Frame 1:** product badge above headline, headline `text-4xl`, decay curve fills container width, stat block stacks below
- **Frame 2:** hero pillar full-width on top, three supporting pillars stack vertically (1-column)
- **Frame 3:** vertical stack with collapsible Wave 1 sub-cards (`[Show 4 parallel agents →]` reveal). Build phase section first, then enforce phase. Severity legend becomes a 3-row compact table.
- **Frame 4:** horizontal swipe carousel with scroll-snap (`scroll-snap-type: x mandatory`), starts on Artifact 1 (hook rejection). Visible scroll-snap indicators (3 dots) below.
- **Frame 5:** hero outcome full-width on top, three supporting outcomes stack vertically. CTA card full-width.
- **Hero scroll-scrubbed heading:** test at 375px viewport — if side-to-side translation overflows, reduce range to ±200px.

**Tablet (768-1024px):**
- Pillar/outcome grid: hero card full-width + 3 supporting in 3-column
- Frame 3: keep two-column build/enforce
- Frame 4: 3 cards in horizontal row (hero spans 2 of 4 columns)

**Desktop (> 1024px):** full design as specified per frame.

**Wide desktop (> 1536px):** content capped at `max-w-7xl mx-auto` — frames don't stretch unbounded.

### SEO Metadata
Update `layout.tsx`:
- Title: *"Archie — Semantic understanding for your codebase"*
- Description: *"Live semantic documentation that enforces itself. Stop your agents from eroding your architecture."*
- OG image: new graphic featuring the four pillars

---

## 8. Migration Plan

### What Carries Over (Reuse Directly)
- `ShaderBackground.tsx` — no changes
- `SmoothScroll.tsx` — no changes
- `MarkdownRenderer.tsx` — no changes (Frame 4 reuses)
- `FileTree.tsx` — no changes (Frame 4 reuses)
- `globals.css` — no changes to design tokens; may extend with new utility classes
- `layout.tsx` — only metadata updates

### What Gets Rewritten
- `app/page.tsx` — full rewrite to the 5-frame structure (v1 page is 823 lines; v2 target is ~600-700 lines with cleaner section components)
- `example-files.ts` + `example-data.json` — refresh content to reflect v2.5+ output (`decision_chain`, `severity_class`, etc.)

### What's New
- `components/PipelineDiagram.tsx` — Frame 3 left column (build phase visualization)
- `components/RuleCard.tsx` — Frame 3 right column (enforcement structure)
- `components/SeverityLegend.tsx` — Frame 3 severity gates
- `components/PillarCard.tsx` — Frame 2 four pillars (also reusable in Frame 5)
- `components/OutcomeCard.tsx` — Frame 5 outcomes (or unify with PillarCard)
- `components/DecayCurve.tsx` — Frame 1 hero visual
- `components/ArtifactCard.tsx` — Frame 4 receipt cards
- `components/CopyableCommand.tsx` — Frame 5 CTA `npx` block

### Asset Requirements
- New OG image (1200x630) reflecting Frame 2 thesis
- Updated `pipeline.png` — replace v1's pipeline diagram with v2's multi-wave visualization (or generate inline as SVG)
- Optional: small video/gif of a hook rejection in real time for Frame 4

### v1 Files to Discard from `landing/`
- `public/pipeline.png` (replaced by inline component or new asset)
- `public/per-folder.png` (no longer used directly — Frame 2 is composed)
- `public/blueprint.png` (no longer used)

---

## 9. Implementation Phases

### Phase 1 — Skeleton (1 PR)
- Strip `landing/app/page.tsx` to a minimal 5-section scaffold
- Update `layout.tsx` metadata
- Verify shader background + smooth scroll still work
- Each frame is a colored placeholder with the section label and headline only
- **Goal:** confirm structure feels right at full scroll

### Phase 2 — Frame 2 + Frame 5 (1 PR)
- Implement the thesis frame and outcomes frame first — these share the four-card pattern (`PillarCard` / `OutcomeCard`)
- These also lock the typography and animation feel for the rest

### Phase 3 — Frame 1 + Frame 3 (1 PR)
- Implement the hook (decay curve, stat block) and the under-the-hood frame (pipeline diagram + rule card)
- These are the most visually custom — biggest design risk concentrated here

### Phase 4 — Frame 4 (1 PR)
- Refresh `example-files.ts` with v2.5+ content
- Implement the three-artifact carousel
- Wire the modal expansion (reuse v1 modal)

### Phase 5 — Polish (1 PR)
- Animation tuning (scroll-scrub feel, fade-up timing)
- Mobile pass (touch targets, simplified pipeline diagram)
- `prefers-reduced-motion` audit
- Accessibility pass
- Performance pass (Lighthouse ≥ 90 across the board)
- Replace v1 OG image

Total: 5 PRs against `feature/landing-v2`. Merge to `main` only after all 5 land and the page is stable.

---

## 10. Open Questions — Resolved

All open questions from the initial PRD draft were resolved during plan-design-review.

| # | Question | Resolution |
|---|---|---|
| 1 | Frame 4 artifact source | **Mock from openmeter repo for now**; Gabor will provide final content once he sees the mocked layout. Implementer should run `/archie-deep-scan` against openmeter or pull plausible artifacts to mock the three cards. |
| 2 | Frame 1 evidence | **Keep v1's Qodo stat block** (65% / 44% / "Not hallucinations. Not model capability. Context.") with citation. |
| 3 | Hero CTA | **Keep v1 wording:** "Analyze your first repo →" with GitHub icon. Literal `npx` command lives only at Frame 5. |
| 4 | Frame 3 pipeline diagram | **Inline SVG/JSX** (`components/PipelineDiagram.tsx`). More control, lighter weight, animatable for arrow draw-ins. |
| 5 | Frame 5 social proof | **Small GitHub star badge** next to repo link in CTA: `★ N on GitHub`. Build-time fetch from GitHub API. If stars < 50, leave off until it earns the badge. |
| 6 | Compound learning angle | **Promoted to Frame 5 hero outcome** ("Your codebase learns"). Anchors the closing argument; no separate callout needed. |

**Implementer notes:**
- Frame 4 mocking: pull representative content from openmeter (https://github.com/openmeterio/openmeter) — pick a deep folder for per-folder CLAUDE.md, fabricate a plausible hook rejection that matches openmeter's actual architecture, and a scan_report.md with realistic findings. Final content will be replaced before launch.
- GitHub star fetch: cache at build time, regenerate on every deploy. No client-side API call (avoids rate limits and CLS).

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 0 | — | — |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR (PLAN) | score: 5/10 → 9/10, 13 decisions |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**UNRESOLVED:** 0
**VERDICT:** DESIGN CLEARED — eng review required before implementation.

---

## 11. Out of Scope

- Multi-language support (English-only for now)
- Dark/light mode toggle (the brand is dark-mode-only — keep it that way)
- Embedded interactive demo (e.g., live `/archie-scan` runner) — too costly for v2; revisit for v3
- Pricing / tiers — Archie is OSS
- Customer testimonials — none yet
- Blog / changelog integration — separate page if/when needed
