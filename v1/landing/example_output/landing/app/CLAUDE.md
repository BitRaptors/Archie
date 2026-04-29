# app/
> Root landing page app: hero section, scroll animations, brutalist UI with neon accents. Static content.

## Patterns

- GSAP ScrollTrigger animations: hero heading moves on scroll, alternating headings pan side-to-side (direction toggled by index parity)
- Parallax images use relative positioning (top: -15%) + height: 130% to create overflow container for scroll effect
- CSS custom properties in @theme block (--color-*, --font-*) exposed to Tailwind; body uses var(--background/--foreground)
- Framer Motion useScroll() + useSpring() creates smooth scroll progress bar with scaleX transform
- Two font families: Space_Mono (monospace, body) + Inter (sans-serif, headings); loaded via next/font/google
- Brutalist UI class chains: border + box-shadow + hover:transform for depth; apply to buttons and cards

## Navigation

**Parent:** [`landing/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `globals.css` | Root styles, theme tokens, Lenis scroll config | Add colors to @theme{} block. Shadow/transform effects in .brutalist-border. |
| `layout.tsx` | RootLayout wraps all pages with fonts and SmoothScroll | Add new Google fonts here. SmoothScroll mounts once at root. |
| `page.tsx` | Landing page: hero, scroll animations, feedback badge | Modify heading text in <h1>, adjust GSAP animation triggers, add new .scrub-heading sections |

## Key Imports

- `from gsap import ScrollTrigger`
- `from framer-motion import useScroll, useSpring`
- `from lucide-react import Github, ArrowRight, ArrowUpRight`

## Add new scrolling section with parallax or side-scroll heading

1. Add HTML with .parallax-img-container or .scrub-heading:not(.hero-heading) class
2. Inside useEffect, add gsap.to() or gsap.fromTo() block with ScrollTrigger config
3. Match start/end timing: 'top bottom' to 'bottom top' for full-viewport scroll
4. Call ctx.revert() on unmount to clean GSAP triggers

## Don't

- Don't hardcode scroll distances (e.g., 500px) — use responsive calc or relative units in GSAP
- Don't mix Framer Motion and GSAP transforms on same element — they fight; use one per component
- Don't forget gsap.context() cleanup in useEffect return — prevents memory leaks on remounts

## Testing

- Scroll page slowly; verify hero heading rotates -5° and moves left. Other headings pan opposite directions.
- Check parallax images move up 25% relative to their containers as page scrolls past.

## Why It's Built This Way

- GSAP ScrollTrigger chosen over Framer Motion scroll for pixel-perfect scrub animations (native scroll hijacking via Lenis)
- Fixed feedback badge in bottom-right: always visible, sticky position lets it persist across scroll sections

## Dependencies

**Exposes to:** `public web`
