"use client"

import { motion } from "framer-motion"
import type { ReactNode } from "react"
import {
  ACCENT_BORDER,
  ACCENT_SHADOW,
  ACCENT_SHADOW_HERO,
  ACCENT_TEXT,
  type AccentColor,
} from "@/lib/design-tokens"

type Props = {
  variant: "hero" | "supporting"
  accent: AccentColor
  icon: ReactNode
  label: string
  description: string
}

export function PillarCard({ variant, accent, icon, label, description }: Props) {
  const isHero = variant === "hero"
  const border = ACCENT_BORDER[accent]
  const shadow = isHero ? ACCENT_SHADOW_HERO[accent] : ACCENT_SHADOW[accent]
  const accentText = ACCENT_TEXT[accent]

  return (
    <motion.div
      whileHover={{ x: isHero ? 6 : 4, y: isHero ? 6 : 4 }}
      transition={{ type: "tween", duration: 0.2, ease: "easeOut" }}
      className={[
        "group relative bg-deep-space-blue-100 border-2",
        border,
        shadow,
        isHero ? "p-12" : "p-8",
        "transition-all flex flex-col gap-4",
      ].join(" ")}
    >
      <div className={`${accentText} transition-transform duration-200 group-hover:rotate-[5deg]`}>
        {icon}
      </div>
      <h3
        className={[
          "font-black uppercase tracking-tight",
          accentText,
          isHero ? "text-3xl md:text-4xl" : "text-xl md:text-2xl",
        ].join(" ")}
      >
        {label}
      </h3>
      <p
        className={[
          "text-gray-300 font-mono leading-relaxed",
          isHero ? "text-base md:text-lg max-w-2xl" : "text-sm",
        ].join(" ")}
      >
        {description}
      </p>
    </motion.div>
  )
}
