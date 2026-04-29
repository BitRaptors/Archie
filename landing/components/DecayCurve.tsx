"use client"

import { motion, useReducedMotion as useFMReducedMotion } from "framer-motion"

// Decay curve SVG: agent velocity drops as drift compounds.
// Animates draw-in on scroll into view; static under prefers-reduced-motion.

const W = 600
const H = 300
const PAD_X = 60
const PAD_Y = 30

// Y values are agent velocity 0..100; X is week 1..12. Curve drops sharply between weeks 4-8.
const POINTS: Array<[number, number]> = [
  [1, 92],
  [2, 90],
  [3, 86],
  [4, 78],
  [5, 65],
  [6, 50],
  [7, 38],
  [8, 28],
  [9, 22],
  [10, 18],
  [11, 14],
  [12, 12],
]

const xScale = (week: number) => PAD_X + ((week - 1) / 11) * (W - PAD_X * 2)
const yScale = (vel: number) => PAD_Y + (1 - vel / 100) * (H - PAD_Y * 2)

const path = POINTS.reduce((acc, [w, v], i) => {
  const x = xScale(w)
  const y = yScale(v)
  return acc + (i === 0 ? `M${x},${y}` : ` L${x},${y}`)
}, "")

const ANNOTATIONS = [
  { week: 1, label: "Week 1: Fresh repo" },
  { week: 6, label: "Week 6: First drift" },
  { week: 12, label: "Week 12: Compounding chaos" },
]

export function DecayCurve() {
  const reduced = useFMReducedMotion()

  return (
    <svg
      role="img"
      aria-label="Agent velocity decays over weeks as architectural drift compounds"
      viewBox={`0 0 ${W} ${H}`}
      className="w-full h-auto"
    >
      {/* Axis labels */}
      <text
        x={PAD_X - 8}
        y={PAD_Y + 6}
        textAnchor="end"
        className="fill-sky-blue font-mono text-[10px] uppercase tracking-widest"
      >
        High
      </text>
      <text
        x={PAD_X - 8}
        y={H - PAD_Y}
        textAnchor="end"
        className="fill-sky-blue font-mono text-[10px] uppercase tracking-widest"
      >
        Low
      </text>
      <text
        x={W / 2}
        y={H - 4}
        textAnchor="middle"
        className="fill-sky-blue font-mono text-[10px] uppercase tracking-[0.3em]"
      >
        Time → Week 1 to Week 12
      </text>

      <text
        x={14}
        y={H / 2}
        textAnchor="middle"
        transform={`rotate(-90, 14, ${H / 2})`}
        className="fill-sky-blue font-mono text-[10px] uppercase tracking-[0.3em]"
      >
        Agent velocity
      </text>

      {/* Grid lines */}
      <line x1={PAD_X} y1={H - PAD_Y} x2={W - PAD_X} y2={H - PAD_Y} stroke="#1a4a5c" strokeWidth="1" />
      <line x1={PAD_X} y1={PAD_Y} x2={PAD_X} y2={H - PAD_Y} stroke="#1a4a5c" strokeWidth="1" />

      {/* Decay curve */}
      <motion.path
        d={path}
        fill="none"
        stroke="#39ff14"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{
          filter: "drop-shadow(0 0 8px rgba(57, 255, 20, 0.6))",
        }}
        initial={reduced ? { pathLength: 1 } : { pathLength: 0 }}
        whileInView={{ pathLength: 1 }}
        viewport={{ once: true, margin: "-15%" }}
        transition={{ duration: reduced ? 0 : 1.5, ease: "easeOut" }}
      />

      {/* Annotation dots + labels */}
      {ANNOTATIONS.map(({ week, label }) => {
        const point = POINTS.find(([w]) => w === week)
        if (!point) return null
        const [, vel] = point
        const cx = xScale(week)
        const cy = yScale(vel)
        const labelAnchor = week === 1 ? "start" : week === 12 ? "end" : "middle"
        const labelX = week === 1 ? cx + 8 : week === 12 ? cx - 8 : cx
        const labelY = cy - 12

        return (
          <g key={week}>
            <circle cx={cx} cy={cy} r="5" fill="#39ff14" />
            <text
              x={labelX}
              y={labelY}
              textAnchor={labelAnchor}
              className="fill-white font-mono text-[10px] uppercase tracking-wider"
            >
              {label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
