"use client"

import { Maximize2 } from "lucide-react"
import type { ReactNode } from "react"
import {
  ACCENT_BORDER,
  ACCENT_SHADOW,
  ACCENT_TEXT,
  type AccentColor,
} from "@/lib/design-tokens"

type Props = {
  filePath: string
  accent: AccentColor
  hero?: boolean
  children: ReactNode
  onExpand?: () => void
}

export function ArtifactCard({ filePath, accent, hero = false, children, onExpand }: Props) {
  const border = ACCENT_BORDER[accent]
  const shadow = ACCENT_SHADOW[accent]
  const text = ACCENT_TEXT[accent]

  return (
    <div
      className={[
        "group relative bg-black border-2 transition-all",
        border,
        shadow,
        "hover:shadow-[4px_4px_0px_0px] hover:translate-x-1 hover:translate-y-1",
        hero ? "lg:col-span-2" : "",
      ].join(" ")}
    >
      {/* Header bar */}
      <div className="border-b border-white/10 px-4 py-2 flex items-center justify-between">
        <span className={`${text} font-mono text-[10px] uppercase tracking-widest truncate`}>
          {">"} {filePath}
        </span>
        {onExpand && (
          <button
            onClick={onExpand}
            aria-label="Expand artifact"
            className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-neon transition-all"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      <div className="p-5 font-mono text-[13px] leading-relaxed text-gray-300 overflow-hidden">
        {children}
      </div>
    </div>
  )
}
