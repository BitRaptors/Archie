import { ArrowUpRight, BookOpen, Github, Shield, TrendingUp, Zap } from "lucide-react"
import { CopyableCommand } from "@/components/CopyableCommand"
import { PillarCard } from "@/components/PillarCard"
import { fetchStars } from "@/lib/github"

export async function Frame5Outcomes() {
  const stars = await fetchStars()

  return (
    <section
      id="frame-5"
      aria-labelledby="frame-5-headline"
      className="relative py-32 md:py-40 px-4 bg-deep-space-blue overflow-hidden border-y-[8px] border-neon"
    >
      {/* Vertical watermark */}
      <div
        className="absolute right-0 top-1/2 -translate-y-1/2 opacity-[0.03] text-neon font-black pointer-events-none select-none uppercase z-0"
        style={{ fontSize: "30vh", lineHeight: "1", writingMode: "vertical-rl" }}
        aria-hidden="true"
      >
        Outcomes
      </div>

      <div className="max-w-7xl mx-auto relative z-10">
        <div className="mb-8">
          <span className="inline-block text-neon font-mono text-xs uppercase tracking-[0.3em] px-2 py-1 bg-neon/10 border-l-2 border-neon">
            04. OUTCOMES
          </span>
        </div>

        <h2
          id="frame-5-headline"
          className="text-4xl md:text-7xl lg:text-8xl font-black text-white uppercase tracking-tighter mb-6 max-w-5xl leading-none"
        >
          Ship faster.
          <br />
          Ship safer.
          <br />
          <span className="text-neon">Forever.</span>
        </h2>

        <p className="text-lg md:text-xl text-gray-300 font-mono max-w-3xl mb-16 md:mb-20">
          Semantic understanding compounds — the longer Archie runs, the sharper it
          gets.
        </p>

        {/* Hero outcome */}
        <div className="mb-8">
          <PillarCard
            variant="hero"
            accent="neon"
            icon={<TrendingUp className="w-12 h-12" strokeWidth={2} />}
            label="Your codebase learns"
            description="Incidents and drift become rules. Agents inherit the scar tissue."
          />
        </div>

        {/* 3 supporting outcomes */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 mb-20 md:mb-24">
          <PillarCard
            variant="supporting"
            accent="sky-blue"
            icon={<Zap className="w-8 h-8" strokeWidth={2} />}
            label="Velocity stays high"
            description="Agents start every task with context, not from scratch."
          />
          <PillarCard
            variant="supporting"
            accent="amber-flame"
            icon={<Shield className="w-8 h-8" strokeWidth={2} />}
            label="No drift to prod"
            description="Hooks catch architectural mistakes before commit."
          />
          <PillarCard
            variant="supporting"
            accent="princeton-orange"
            icon={<BookOpen className="w-8 h-8" strokeWidth={2} />}
            label="Decisions preserved"
            description="The why survives every refactor."
          />
        </div>

        {/* CTA block */}
        <div className="bg-black border-4 border-neon p-10 md:p-14 max-w-4xl mx-auto -rotate-1 hover:rotate-0 transition-transform shadow-[12px_12px_0px_0px_#39ff14]">
          <h3 className="text-3xl md:text-4xl font-black uppercase text-white mb-4 leading-tight">
            Stop watching your codebase erode.
          </h3>
          <p className="text-base md:text-lg text-gray-300 font-mono mb-8 leading-relaxed">
            Three minutes to install. Compounding returns from day one.
          </p>

          <CopyableCommand command="npx @bitraptors/archie ." />

          <div className="mt-8 flex items-center gap-6 flex-wrap">
            <a
              href="https://github.com/BitRaptors/Archie"
              className="inline-flex items-center gap-2 text-sky-blue font-mono text-sm uppercase tracking-widest hover:text-neon transition-colors group"
            >
              <Github className="w-4 h-4" />
              View on GitHub
              <ArrowUpRight className="w-4 h-4 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
              {stars !== null && stars >= 50 && (
                <span className="text-amber-flame ml-1">★ {stars}</span>
              )}
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
