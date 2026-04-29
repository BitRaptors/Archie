"use client"

import { Github } from "lucide-react"
import { useEffect, useRef } from "react"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import { ShaderBackground } from "@/components/ShaderBackground"
import { ProductBadge } from "@/components/ProductBadge"
import { DecayCurve } from "@/components/DecayCurve"
import { StatBlock } from "@/components/StatBlock"
import { useReducedMotion } from "@/hooks/useReducedMotion"

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger)
}

export function Frame1Hero() {
  const ref = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()

  useEffect(() => {
    if (reduced) return
    if (!ref.current) return
    const ctx = gsap.context(() => {
      const heading = ref.current!.querySelector(".hero-heading")
      if (!heading) return
      gsap.to(heading, {
        x: () => -((heading as HTMLElement).scrollWidth - window.innerWidth) / 4,
        rotation: -3,
        ease: "none",
        scrollTrigger: {
          trigger: heading,
          start: "top center",
          end: "bottom top",
          scrub: 1,
        },
      })
    }, ref)
    return () => ctx.revert()
  }, [reduced])

  return (
    <header
      ref={ref}
      id="frame-1"
      aria-labelledby="frame-1-headline"
      className="min-h-screen relative flex flex-col px-4 overflow-hidden"
    >
      <ShaderBackground />
      <div
        className="absolute inset-0 z-0 opacity-20 pointer-events-none"
        style={{
          backgroundImage: "radial-gradient(#39ff14 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      {/* Vertical watermark */}
      <div
        className="absolute right-2 top-1/2 -translate-y-1/2 opacity-[0.04] text-amber-flame font-black pointer-events-none select-none uppercase z-0"
        style={{ fontSize: "20vh", lineHeight: "1", writingMode: "vertical-rl" }}
        aria-hidden="true"
      >
        Erosion
      </div>

      <div className="relative z-10 flex-1 flex flex-col justify-center max-w-7xl mx-auto w-full pt-24 pb-16">
        <ProductBadge />
        <h1
          id="frame-1-headline"
          className="hero-heading text-4xl md:text-7xl lg:text-8xl font-black uppercase tracking-tighter mix-blend-difference text-neon mb-12 max-w-6xl"
        >
          Agent-built codebases
          <br />
          erode faster than agents
          <br />
          can patch them.
        </h1>
        <p className="text-xl md:text-2xl text-gray-300 mb-12 max-w-3xl border-l-4 border-neon pl-6 bg-black/40 py-6 backdrop-blur-sm">
          Without semantic understanding, every PR drifts a little further from the
          architecture you started with — and agents have no way to know.
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-12 items-start">
          <div className="lg:col-span-3 border-2 border-neon/30 bg-black/60 p-6 backdrop-blur-sm">
            <DecayCurve />
          </div>
          <div className="lg:col-span-2">
            <StatBlock />
          </div>
        </div>

        <div className="mt-16 flex items-center gap-6">
          <a
            href="https://github.com/BitRaptors/Archie"
            className="inline-flex items-center gap-3 px-6 py-4 md:px-8 md:py-5 bg-deep-space-blue text-neon font-bold text-base md:text-lg uppercase tracking-wider border-2 border-neon shadow-[8px_8px_0px_0px_#39ff14] hover:shadow-[4px_4px_0px_0px_#39ff14] hover:translate-x-1 hover:translate-y-1 hover:bg-neon hover:text-deep-space-blue transition-all"
          >
            <Github className="w-6 h-6" />
            Analyze your first repo →
          </a>
          <span className="text-gray-400 font-mono text-xs uppercase tracking-[0.3em] hidden md:block">
            Or scroll to see how ↓
          </span>
        </div>
      </div>
    </header>
  )
}
