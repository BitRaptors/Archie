import { ArrowRight, Search, Sparkles } from "lucide-react"

export function Frame2Thesis() {
  return (
    <section
      id="frame-2"
      aria-labelledby="frame-2-headline"
      className="relative min-h-screen flex flex-col justify-center py-20 md:py-28 px-4 bg-deep-space-blue overflow-hidden border-t-4 border-neon"
    >
      {/* Vertical watermark */}
      <div
        className="absolute right-0 top-1/2 -translate-y-1/2 opacity-[0.03] text-neon font-black pointer-events-none select-none uppercase z-0"
        style={{ fontSize: "30vh", lineHeight: "1", writingMode: "vertical-rl" }}
        aria-hidden="true"
      >
        Understanding
      </div>

      <div className="max-w-7xl mx-auto relative z-10 w-full">
        {/* Section number */}
        <div className="mb-8">
          <span className="inline-block text-neon font-mono text-xs uppercase tracking-[0.3em] px-2 py-1 bg-neon/10 border-l-2 border-neon">
            01. THE THESIS
          </span>
        </div>

        {/* Headline */}
        <h2
          id="frame-2-headline"
          className="text-3xl md:text-4xl lg:text-5xl font-black text-white uppercase tracking-tight mb-4 max-w-5xl"
        >
          Archie builds{" "}
          <span className="text-neon underline decoration-neon decoration-4 underline-offset-8">
            semantic understanding
          </span>{" "}
          of your codebase.
        </h2>

        <p className="text-base md:text-lg text-gray-300 font-mono max-w-3xl mb-12">
          Curated knowledge, delivered exactly where and when agents need it.
        </p>

        {/* Beat 1: grep vs curated contrast */}
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-4 md:gap-6 items-stretch mb-10 md:mb-12">
          {/* Without Archie */}
          <div className="border-2 border-amber-flame/50 bg-black/40 p-5 md:p-6 flex items-start gap-4">
            <Search className="w-6 h-6 text-amber-flame flex-shrink-0 mt-0.5" strokeWidth={2} />
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-amber-flame mb-2">
                Without Archie
              </div>
              <div className="font-black text-white text-lg md:text-xl uppercase tracking-tight mb-1 leading-tight">
                Agents grep to guess
              </div>
              <div className="font-mono text-xs md:text-sm text-gray-400 leading-relaxed">
                Every session starts with the agent searching your codebase to
                reverse-engineer the rules.
              </div>
            </div>
          </div>

          {/* Arrow */}
          <div className="hidden md:flex items-center justify-center">
            <ArrowRight className="w-8 h-8 text-neon" strokeWidth={2.5} aria-hidden="true" />
          </div>

          {/* With Archie */}
          <div className="border-2 border-neon bg-black/40 p-5 md:p-6 flex items-start gap-4 shadow-[6px_6px_0px_0px_#39ff14]">
            <Sparkles className="w-6 h-6 text-neon flex-shrink-0 mt-0.5" strokeWidth={2} />
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-neon mb-2">
                With Archie
              </div>
              <div className="font-black text-white text-lg md:text-xl uppercase tracking-tight mb-1 leading-tight">
                Curated answers, ready
              </div>
              <div className="font-mono text-xs md:text-sm text-gray-300 leading-relaxed">
                The right context surfaces at the file the agent is touching.
                No grep, no guessing, no drift.
              </div>
            </div>
          </div>
        </div>

        {/* Beat 2: the payoff — agents inherit how it was built */}
        <div className="border-2 border-neon bg-deep-space-blue-100 shadow-[12px_12px_0px_0px_#39ff14] p-6 md:p-8 max-w-5xl">
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-amber-flame mb-3">
            The payoff
          </div>
          <h3 className="text-2xl md:text-3xl lg:text-4xl font-black text-white uppercase tracking-tight mb-3 leading-tight">
            Agents inherit how it was built.
          </h3>
          <p className="text-gray-300 font-mono text-sm md:text-base leading-relaxed">
            Every architectural decision, every pattern, every piece of reasoning —
            preserved and followed automatically. Not just the code.
          </p>
        </div>
      </div>
    </section>
  )
}
