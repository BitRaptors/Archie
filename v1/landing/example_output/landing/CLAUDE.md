# landing/
> Next.js landing page root with GSAP scroll animations, shader backgrounds, brutalist UI design.

## Patterns

- GSAP ScrollTrigger: hero heading animates on scroll, alternating elements pan horizontally (direction toggled by index % 2)
- Parallax images use overflow containers (height: 130%) + relative positioning (top: -15%) for scroll effect
- Canvas shader backgrounds rendered client-side with hardcoded tuning props, composited with opacity overlay div
- Next.js App Router config minimal — no custom middleware, relies on child app/ and components/ for logic
- ESLint extends next/core-web-vitals + next/typescript with custom globalIgnores override for .next/, out/, build/

## Navigation

**Parent:** [`root/`](../CLAUDE.md)
**Peers:** [`backend/`](../backend/CLAUDE.md) | [`frontend/`](../frontend/CLAUDE.md)
**Children:** [`app/`](app/CLAUDE.md) | [`components/`](components/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `next.config.ts` | Next.js build configuration | Add canvas/shader optimizations, image loaders, or production builds here |
| `tsconfig.json` | TypeScript compiler settings | Ensure strict mode enabled; check lib array for DOM/DOM.Iterable support |
| `package.json` | Dependencies: GSAP, Three.js, Shadergradient, Framer Motion, Lenis | Lock major versions; gsap ScrollTrigger requires 'gsap' package, not separate plugin |
| `eslint.config.mjs` | Linting rules for Next.js + TypeScript | Preserve globalIgnores override; add rules if brutalist CSS patterns cause false positives |

## Key Imports

- `import gsap, { ScrollTrigger } from 'gsap' (register plugin in useEffect)`
- `import { ShaderGradient } from 'shadergradient' (canvas background)`
- `import { useRef, useEffect } from 'react' (animation refs + lifecycle)`

## Add new animated hero section to landing

1. Create component extending app/page.tsx pattern: GSAP ScrollTrigger + parallax overflow div
2. Import ShaderGradient from components/, pass hardcoded shader config object
3. Wrap content in <div className='relative h-screen overflow-hidden'>, nest parallax image with height: 130%
4. Call gsap.registerPlugin(ScrollTrigger) in useEffect, trigger on window resize with ScrollTrigger.refresh()

## Don't

- Don't dynamically pass shader props from state — hardcode tuned values in components/; shader recompiles on prop change
- Don't animate SVG/DOM parallax — use CSS transform + overflow container with fixed top offset instead
- Don't skip ScrollTrigger.refresh() after DOM mutations — animations won't trigger on new elements

## Testing

- Open DevTools: verify hero heading moves smoothly on scroll, no jank on 60fps throttle
- Check mobile: parallax images scale correctly, GSAP animations don't block scroll performance

## Why It's Built This Way

- Hardcoded shader props: avoids recompilation cost; tuning happens once, not per-render
- Lenis + GSAP ScrollTrigger: smooth scroll hijacking + native scroll-linked animations (no competing scroll libs)

## Dependencies

**Exposes to:** `public web`

## Subfolders

- [`app/`](app/CLAUDE.md) — Marketing site with Three.js shader background and GSAP scroll animations
- [`components/`](components/CLAUDE.md) — Marketing site with Three.js shader background and GSAP scroll animations
