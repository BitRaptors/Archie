import { Activity, ArrowUpRight, CalendarCheck, Github, Timer } from "lucide-react"
import { CopyableCommand } from "@/components/CopyableCommand"
import { PillarCard } from "@/components/PillarCard"
import { fetchStars } from "@/lib/github"

export async function Frame5Outcomes() {
  const stars = await fetchStars()

  return (
    <section
      id="frame-5"
      aria-labelledby="frame-5-headline"
      className="relative min-h-screen flex flex-col justify-center px-4 py-12 bg-deep-space-blue overflow-hidden border-y-[8px] border-neon"
    >
      {/* Vertical watermark */}
      <div
        className="absolute right-0 top-1/2 -translate-y-1/2 opacity-[0.03] text-neon font-black pointer-events-none select-none uppercase z-0"
        style={{ fontSize: "25vh", lineHeight: "1", writingMode: "vertical-rl" }}
        aria-hidden="true"
      >
        Outcomes
      </div>

      <div className="max-w-7xl mx-auto relative z-10 w-full">
        {/* Header row — section number + headline + subhead, all compact */}
        <div className="grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-8 lg:gap-12 items-end mb-10 md:mb-12">
          <div>
            <span className="inline-block text-neon font-mono text-xs uppercase tracking-[0.3em] px-2 py-1 bg-neon/10 border-l-2 border-neon mb-4">
              04. OUTCOMES
            </span>
            <h2
              id="frame-5-headline"
              className="text-3xl md:text-5xl lg:text-6xl font-black text-white uppercase tracking-tighter max-w-5xl leading-[0.95]"
            >
              Ship <span className="text-neon">faster.</span>
              <br />
              Ship <span className="text-neon">safer.</span>
            </h2>
          </div>
          <p className="text-base md:text-lg text-gray-300 font-mono leading-relaxed">
            Better codebase → better uptime → more money in the bank.{" "}
            <span className="text-neon">Here&apos;s how Archie compounds into dollars.</span>
          </p>
        </div>

        {/* 3 money mechanisms */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 mb-8 md:mb-10">
          <PillarCard
            variant="supporting"
            accent="sky-blue"
            icon={<CalendarCheck className="w-7 h-7" strokeWidth={2} />}
            label="Stable release cadence"
            description="Agents land grounded code consistently. Predictable shipping, no surprise firedrills derailing the schedule."
          />
          <PillarCard
            variant="supporting"
            accent="amber-flame"
            icon={<Activity className="w-7 h-7" strokeWidth={2} />}
            label="Less downtime cost"
            description="Architectural mistakes caught at edit time, not at 3am. Real uptime, real money saved on incidents."
          />
          <PillarCard
            variant="supporting"
            accent="princeton-orange"
            icon={<Timer className="w-7 h-7" strokeWidth={2} />}
            label="Cut validation overhead"
            description="Agents land grounded code. Reclaim weeks of dev time from validating AI output."
          />
        </div>

        {/* CTA — single row layout, no rotation, tight */}
        <div className="bg-black border-2 border-neon shadow-[8px_8px_0px_0px_#39ff14] p-5 md:p-6 max-w-5xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-5 md:gap-8 items-center">
            <div>
              <h3 className="text-xl md:text-2xl font-black uppercase text-white mb-1 leading-tight">
                Stop watching your codebase erode.
              </h3>
              <p className="text-xs md:text-sm text-gray-400 font-mono">
                Three minutes to install. Compounding returns from day one.
              </p>
            </div>
            <div className="flex flex-col gap-3 items-stretch md:items-end w-full md:w-auto">
              <CopyableCommand command="npx @bitraptors/archie ." />
              <a
                href="https://github.com/BitRaptors/Archie"
                className="inline-flex items-center gap-2 text-sky-blue font-mono text-xs uppercase tracking-widest hover:text-neon transition-colors group justify-end"
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
      </div>
    </section>
  )
}
