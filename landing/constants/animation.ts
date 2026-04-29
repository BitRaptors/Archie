// Centralized animation timing. Mirrors landing/DESIGN.md.
// All animated components should import from here, not hardcode values.

export const FADE_UP_INITIAL = { y: 100, opacity: 0 } as const
export const FADE_UP_VISIBLE = { y: 0, opacity: 1 } as const
export const FADE_UP_TRANSITION = {
  duration: 1.5,
  ease: [0.215, 0.61, 0.355, 1],
} as const

// GSAP scroll-trigger config used across scroll-scrubbed headings
export const SCROLL_SCRUB = {
  scrub: 1,
  start: "top center",
  end: "bottom top",
} as const

// Framer Motion spring physics for the raptor and modal transitions
export const SPRING = {
  type: "spring",
  stiffness: 260,
  damping: 20,
} as const

// Card hover transition
export const HOVER_TRANSITION = "all 0.2s ease"

// Stagger between siblings when 3+ animate together
export const STAGGER_MS = 100

// Decay curve draw-in duration (Frame 1)
export const DECAY_CURVE_DRAW_S = 1.5
