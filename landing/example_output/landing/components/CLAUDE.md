# components/
> Landing page visual components: shader-based animated backgrounds and smooth scroll behavior for hero sections.

## Patterns

- Client-side canvas rendering with hardcoded shader props object — tuned values, not dynamic config
- Gradient overlay (div with opacity) composited over shader canvas to control final visual tone
- useEffect RAF loop for continuous animation — manual cleanup via lenis.destroy() on unmount
- SmoothScroll is a mount-only hook wrapper (returns null) — meant for single app-wide instantiation
- Shader props use snake_case keys matching shadergradient library API exactly — typos break rendering

## Navigation

**Parent:** [`landing/`](../CLAUDE.md)
**Peers:** [`app/`](../app/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `ShaderBackground.tsx` | Animated gradient backdrop with dual-layer compositing | Adjust gradientProps object values; tweak overlay opacity for contrast |
| `SmoothScroll.tsx` | Global scroll smoothing via Lenis; zero UI output | Modify duration/easing; ensure single instantiation per app tree |

## Key Imports

- `from 'shadergradient' import ShaderGradientCanvas, ShaderGradient`
- `from 'lenis' import Lenis (no named export; default class)`

## Adjust shader gradient colors or animation speed for brand consistency

1. Edit color1, color2, color3 hex values in gradientProps
2. Tune uSpeed (0.2 = slow), uFrequency (5.5 = wave density), rotationY (10 = spin)
3. Adjust overlay opacity to control visual depth; test in production (canvas rendering differs locally)

## Don't

- Don't instantiate Lenis multiple times — RAF loop overhead & memory leaks; mount SmoothScroll once at app root
- Don't modify gradientProps inside render — hardcoded object prevents unnecessary re-renders and prop thrashing
- Don't omit z-index layering — absolute positioning + z-0/z-1 stacking is load-bearing for visual hierarchy

## Testing

- Verify Lenis cleanup: check DevTools → Memory → heap snapshots for RAF loop termination on unmount
- Visual regression: shader output GPU-dependent; test on target device; grain + pixelDensity affect performance

## Debugging

- ShaderGradientCanvas silent failures: check browser console for WebGL errors; shadergradient props are strict
- Lenis stutter: conflicts with other scroll libraries (gsap ScrollTrigger, react-scroll); disable/isolate one smoothing layer

## Why It's Built This Way

- Lenis duration=1.2s + custom easing curve chosen for premium feel — longer than default, matches landing aesthetic
- Shader grain=on + low pixelDensity=1: balances visual quality vs performance; adjust for lower-end devices

## Dependencies

**Exposes to:** `public web`
