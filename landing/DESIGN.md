# Archie Landing — Design System

**Status:** v2 baseline · Source of truth for all `landing/` work.

This doc captures the design vocabulary inherited from v1 (preserved in `v1/landing/`) and locked for v2. Update this file when design decisions change; do not bury new tokens in component code.

---

## Color Tokens

Defined in `app/globals.css` under `@theme`. Use Tailwind utility classes via these tokens — never hex literals in components.

| Token | Hex | Use |
|---|---|---|
| `--color-neon` | `#39ff14` | Primary accent · CTAs · borders · emphasis · hero outcome |
| `--color-sky-blue` | `#8ecae6` | Secondary accent · annotations · code highlights · supporting pillars |
| `--color-blue-green` | `#219ebc` | Tertiary accent · pipeline diagrams · build phase |
| `--color-deep-space-blue` | `#023047` | Primary background |
| `--color-deep-space-blue-100` | `#00090e` | Deeper background (alternating sections + cards) |
| `--color-amber-flame` | `#ffb703` | Warning · highlight · stats · supporting accent |
| `--color-princeton-orange` | `#fb8500` | Critical CTA · severity escalation (blocks) · supporting accent |
| `--foreground` | `#e8f4fa` | Body text (hero, headings) |
| `gray-300` | `#D1D5DB` | Default body text on dark backgrounds (8:1+ contrast vs deep-space-blue, AAA) |
| `gray-400` | `#9CA3AF` | **Avoid for body text** — fails AA contrast on deep-space-blue. Use only for de-emphasized labels |

**Forbidden:** purple, violet, indigo, magenta. Period. The palette is the brand.

---

## Typography

| Family | Variable | Weight | Use |
|---|---|---|---|
| **Inter** | `--font-sans` | 900 (black) | All headings · uppercase · tight tracking |
| **Space Mono** | `--font-mono` | 400 / 700 | Body text · code · labels · annotations |

**Type scale (inherits Tailwind defaults, used as below):**

| Element | Mobile | Tablet | Desktop | Style |
|---|---|---|---|---|
| Hero headline (Frame 1) | `text-4xl` | `text-8xl` | `text-9xl` | Inter Black, uppercase, `tracking-tighter`, `mix-blend-difference` |
| Section H2 (Frames 2-5) | `text-3xl` | `text-5xl` | `text-7xl` | Inter Black, uppercase |
| Pillar/outcome label (hero) | `text-2xl` | `text-3xl` | `text-4xl` | Inter Black, uppercase |
| Pillar/outcome label (supporting) | `text-xl` | `text-xl` | `text-2xl` | Inter Black, uppercase |
| Body | `text-base` | `text-xl` | `text-xl` | Space Mono, regular |
| Section number chip | `text-sm` | `text-sm` | `text-sm` | Space Mono, uppercase, `tracking-widest` |
| Terminal card body | `text-[13px]` | `text-[13px]` | `text-[13px]` | Space Mono, `leading-relaxed` |

---

## Style Language

The brand is **brutalist + glassy + neon over deep space**. Every component should pass these tests:

- **Brutalist borders:** `2px solid <accent>` + `8px 8px 0px 0px <accent>` offset shadow. On hover: shadow shrinks to `4px 4px`, element translates `(4px, 4px)`. Transition: `0.2s ease`.
- **Hero variant:** `12px 12px` shadow, `(6px, 6px)` translate on hover.
- **Glassy cards:** `bg-deep-space-blue/60` + `backdrop-blur-xl` for premium depth on dark backgrounds.
- **Neon glow on key text:** `text-shadow: 0 0 10px rgba(57, 255, 20, 0.5), 0 0 20px rgba(57, 255, 20, 0.3)` — use sparingly (hero, primary CTA).
- **Mix-blend-difference** on hero headline so it punches through the shader.
- **Per-section accent:** each frame leans on one secondary color. Don't mix accents within a card.
- **Vertical text watermarks** (background): `writingMode: vertical-rl`, opacity 0.02-0.05, e.g., "MEMORY", "PIPELINE", "OUTCOMES".
- **Section numbering:** `01.`, `02.`, `03.` style chips — neon-on-neon/10, uppercase, `tracking-widest`, left-bordered.

**Spacing:** Tailwind's default scale. Section padding `py-32 md:py-40`, content max-width `max-w-7xl mx-auto`.

**Border radius:** zero on all elements except the modal close button (per v1 — single exception).

---

## Animation Principles

- **Scroll-scrubbed headings:** GSAP `ScrollTrigger`, `scrub: 1`, `start: "top center"`, `end: "bottom top"`, side-to-side translation
- **Parallax images:** containers `overflow-hidden`, inner `25%` Y-translation on scroll
- **Fade-up reveals:** `from { y: 100, opacity: 0 }`, triggered at `top 85%`, `duration: 1.5s`, `ease: power4.out`, `toggleActions: "play none none reverse"`
- **Spring physics:** Framer Motion `stiffness: 260, damping: 20` for the raptor and modal transitions
- **Smooth scroll:** Lenis (wired in `SmoothScroll.tsx`)
- **Card hover:** `0.2s ease` on shadow + transform
- **Stagger:** 100ms between siblings when 3+ animate together
- **Animation budget:** at most 3 simultaneous animations per scroll viewport

### `prefers-reduced-motion` policy

When set:
- **Disable:** scroll-scrubbed translations, parallax, draw-in animations (decay curve, pipeline arrows), raptor spring
- **Keep:** fade-up reveals, hover effects, scroll progress bar, shader background
- **Replace:** scroll-scrubbed headings render at final position; SVG diagrams render fully drawn

Implementation: gate GSAP `ScrollTrigger` registrations behind `window.matchMedia('(prefers-reduced-motion: reduce)').matches`.

---

## AI Slop Guard

These patterns are **forbidden**. Designer/dev must check work against this list before committing:

1. ❌ Symmetric 4-card grids (use hero + 3 supporting instead)
2. ❌ Icons inside colored circles (use flat icons in accent color)
3. ❌ Centered text on every section (left-align by default)
4. ❌ Bubbly border-radius (zero radius is the brand)
5. ❌ Decorative blobs, floating circles, wavy SVG dividers
6. ❌ Emoji as design elements (footer ❤️ is the single exception)
7. ❌ Generic hero copy ("Welcome to Archie")
8. ❌ Cookie-cutter section rhythm (hero → 3-features → testimonials → pricing → CTA)
9. ❌ Purple/violet/indigo gradients (palette is locked)
10. ❌ Stock imagery, "happy people" photos

When a new component pattern emerges, run it past this list before merging.

---

## Empty-State Warmth Principle

Empty states are features. Each empty state has:
1. **Visual:** an icon (not just text) — `Folder`, `Search`, `FileText` from Lucide
2. **Copy:** what's not here + why
3. **Primary action:** a link or button forward (run a command, view docs, retry)

"No files found." is not a design.
"No CLAUDE.md generated yet — run `/archie-deep-scan` to populate. [View docs →]" is.

---

## Component Inventory (canonical reuse)

| Component | File | Use |
|---|---|---|
| `ShaderBackground` | `components/ShaderBackground.tsx` | Hero animated background |
| `SmoothScroll` | `components/SmoothScroll.tsx` | Lenis wrapper, root-level |
| `MarkdownRenderer` | `components/MarkdownRenderer.tsx` | Render `.md` content (Frame 4 + modal) |
| `FileTree` | `components/FileTree.tsx` | File browser (Frame 4 modal) |

When v2 adds new components (e.g., `PillarCard`, `RuleCard`, `DecayCurve`), add them to this table.

---

## Selection Color

`::selection { background: #39ff14; color: #000; }` — keeps the neon brand in copy-paste.
