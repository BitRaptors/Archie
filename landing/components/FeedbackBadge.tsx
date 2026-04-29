"use client"

import { motion } from "framer-motion"
import { useState } from "react"

export function FeedbackBadge() {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onPointerEnter={() => setHovered(true)}
      onPointerLeave={() => setHovered(false)}
      className="fixed bottom-6 right-6 z-50 flex flex-col items-center pointer-events-auto overflow-visible"
    >
      {/* Raptor easter egg — pointer-events-none so it doesn't capture clicks
          and you can move the cursor onto it without leaving the wrapper. */}
      <motion.div
        initial={{ y: 60, opacity: 0 }}
        animate={{ y: hovered ? -40 : 60, opacity: hovered ? 1 : 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 20 }}
        className="w-24 h-24 mb-[-20px] overflow-visible pointer-events-none"
        aria-hidden="true"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/raptor.svg"
          alt=""
          loading="eager"
          className="w-full h-full object-contain drop-shadow-[0_0_15px_rgba(57,255,20,0.5)]"
        />
      </motion.div>

      <a
        href="https://github.com/BitRaptors/Archie/issues"
        target="_blank"
        rel="noopener noreferrer"
        className="relative z-10 transform hover:-translate-y-1 hover:scale-105 transition-all"
      >
        <div className="bg-neon text-black font-black uppercase tracking-widest px-4 py-2 border-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] flex flex-col items-center gap-1 text-xs">
          <div className="flex items-center gap-2 border-b border-black/20 pb-1 w-full justify-center">
            <span className="animate-pulse w-2 h-2 bg-black rounded-full block" />
            PREVIEW
          </div>
          <span>SEND FEEDBACK</span>
        </div>
      </a>
    </div>
  )
}
