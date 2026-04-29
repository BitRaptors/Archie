"use client"

import { Github } from "lucide-react"
import { useEffect, useRef } from "react"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import { ShaderBackground } from "@/components/ShaderBackground"
import { ProductBadge } from "@/components/ProductBadge"
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
        x: () => -((heading as HTMLElement).scrollWidth - window.innerWidth) / 6,
        rotation: -2,
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
      className="relative min-h-screen flex flex-col justify-center overflow-hidden px-4 py-16"
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

      <div className="relative z-10 max-w-7xl mx-auto w-full">
        <ProductBadge />
        <h1
          id="frame-1-headline"
          className="hero-heading text-3xl sm:text-5xl md:text-6xl lg:text-7xl font-black uppercase tracking-tighter mix-blend-difference text-neon mb-8 max-w-6xl leading-[0.95]"
        >
          Agent-built codebases
          <br />
          tend to erode over time.
        </h1>
        <p className="text-base md:text-lg text-gray-300 mb-8 max-w-2xl border-l-4 border-neon pl-4 md:pl-6 bg-black/40 py-4 md:py-5 backdrop-blur-sm">
          Without an architecturally sound foundation, they can quickly become
          unmaintainable, and the speed agents bring to development starts to fade.
        </p>

        <p className="text-xl md:text-2xl lg:text-3xl font-black uppercase tracking-tight text-white mb-10 max-w-3xl leading-tight">
          You can&apos;t develop what you{" "}
          <span className="text-neon underline decoration-neon decoration-4 underline-offset-[6px]">
            can&apos;t understand.
          </span>
        </p>

        <a
          href="https://github.com/BitRaptors/Archie"
          className="inline-flex items-center gap-3 px-5 py-3 md:px-6 md:py-4 bg-deep-space-blue text-neon font-bold text-sm md:text-base uppercase tracking-wider border-2 border-neon shadow-[8px_8px_0px_0px_#39ff14] hover:shadow-[4px_4px_0px_0px_#39ff14] hover:translate-x-1 hover:translate-y-1 hover:bg-neon hover:text-deep-space-blue transition-all w-fit"
        >
          <Github className="w-5 h-5" />
          Analyze your first repo →
        </a>
      </div>
    </header>
  )
}
