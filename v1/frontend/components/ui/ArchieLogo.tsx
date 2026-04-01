import { useEffect, useRef, useState, useCallback } from 'react'

interface ArchieLogoProps {
  size?: number
  className?: string
}

const LEFT_EYE = { cx: 79, cy: 88 }
const RIGHT_EYE = { cx: 121, cy: 88 }
const MAX_OFFSET = 5
// Default pupil offset from eye center (as in the static SVG)
const DEFAULT_PUPIL_OFFSET = { dx: 4, dy: 3 }
// Shine offset relative to pupil position
const SHINE_OFFSET = { dx: 3, dy: -4 }

export function ArchieLogo({ size = 40, className }: ArchieLogoProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [pupilOffset, setPupilOffset] = useState(DEFAULT_PUPIL_OFFSET)
  const rafRef = useRef<number>(0)

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)

    rafRef.current = requestAnimationFrame(() => {
      const svg = svgRef.current
      if (!svg) return

      const rect = svg.getBoundingClientRect()
      const svgCenterX = rect.left + rect.width / 2
      const svgCenterY = rect.top + rect.height / 2

      // Use the midpoint between both eyes as reference
      const midEyeX = (LEFT_EYE.cx + RIGHT_EYE.cx) / 2
      const midEyeY = (LEFT_EYE.cy + RIGHT_EYE.cy) / 2

      // Map cursor position relative to SVG center, normalized to viewBox scale
      const scale = 200 / rect.width
      const dx = (e.clientX - svgCenterX) * scale
      const dy = (e.clientY - svgCenterY) * scale

      const angle = Math.atan2(dy, dx)
      const distance = Math.sqrt(dx * dx + dy * dy)
      const clampedDist = Math.min(distance / 40, 1) // normalize

      setPupilOffset({
        dx: Math.cos(angle) * MAX_OFFSET * clampedDist,
        dy: Math.sin(angle) * MAX_OFFSET * clampedDist,
      })
    })
  }, [])

  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [handleMouseMove])

  const leftPupil = { cx: LEFT_EYE.cx + pupilOffset.dx, cy: LEFT_EYE.cy + pupilOffset.dy }
  const rightPupil = { cx: RIGHT_EYE.cx + pupilOffset.dx, cy: RIGHT_EYE.cy + pupilOffset.dy }
  const leftShine = { cx: leftPupil.cx + SHINE_OFFSET.dx, cy: leftPupil.cy + SHINE_OFFSET.dy }
  const rightShine = { cx: rightPupil.cx + SHINE_OFFSET.dx, cy: rightPupil.cy + SHINE_OFFSET.dy }

  return (
    <svg
      ref={svgRef}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 200 200"
      width={size}
      height={size}
      className={className}
    >
      <defs>
        <linearGradient id="ghostGrad" x1="20%" y1="0%" x2="80%" y2="100%">
          <stop offset="0%" style={{ stopColor: '#8ED8F5', stopOpacity: 1 }} />
          <stop offset="100%" style={{ stopColor: '#3AACE0', stopOpacity: 1 }} />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="4" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Ghost body */}
      <path
        d="M 40 105 C 40 63, 68 32, 100 32 C 132 32, 160 63, 160 105 L 160 162 C 151 155, 142 148, 133 155 C 124 162, 115 155, 100 155 C 85 155, 76 162, 67 155 C 58 148, 49 155, 40 162 Z"
        fill="url(#ghostGrad)"
        filter="url(#glow)"
      />

      {/* Blueprint grid lines */}
      <g opacity="0.15" stroke="#ffffff" strokeWidth="1.2" strokeDasharray="4,3">
        <line x1="60" y1="85" x2="140" y2="85" />
        <line x1="55" y1="110" x2="145" y2="110" />
        <line x1="60" y1="135" x2="140" y2="135" />
        <line x1="78" y1="55" x2="78" y2="150" />
        <line x1="100" y1="42" x2="100" y2="152" />
        <line x1="122" y1="55" x2="122" y2="150" />
      </g>

      {/* Eye whites */}
      <ellipse cx={LEFT_EYE.cx} cy={LEFT_EYE.cy} rx="14" ry="15" fill="white" />
      <ellipse cx={RIGHT_EYE.cx} cy={RIGHT_EYE.cy} rx="14" ry="15" fill="white" />

      {/* Pupils */}
      <ellipse cx={leftPupil.cx} cy={leftPupil.cy} rx="7" ry="8" fill="#1A2E4A" />
      <ellipse cx={rightPupil.cx} cy={rightPupil.cy} rx="7" ry="8" fill="#1A2E4A" />

      {/* Eye shines */}
      <circle cx={leftShine.cx} cy={leftShine.cy} r="2.5" fill="white" />
      <circle cx={rightShine.cx} cy={rightShine.cy} r="2.5" fill="white" />
    </svg>
  )
}
