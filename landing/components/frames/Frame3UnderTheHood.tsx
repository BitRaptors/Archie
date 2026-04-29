import { PipelineDiagram } from "@/components/PipelineDiagram"
import { RuleCard } from "@/components/RuleCard"
import { SeverityLegend } from "@/components/SeverityLegend"

export function Frame3UnderTheHood() {
  return (
    <section
      id="frame-3"
      aria-labelledby="frame-3-headline"
      className="relative py-32 md:py-40 px-4 bg-deep-space-blue-100 overflow-hidden border-t-4 border-sky-blue"
    >
      {/* Vertical watermark */}
      <div
        className="absolute -left-10 top-1/2 -translate-y-1/2 opacity-[0.03] text-sky-blue font-black pointer-events-none select-none uppercase z-0"
        style={{ fontSize: "30vh", lineHeight: "1", writingMode: "vertical-rl" }}
        aria-hidden="true"
      >
        Pipeline
      </div>

      <div className="max-w-7xl mx-auto relative z-10">
        <div className="mb-8">
          <span className="inline-block text-sky-blue font-mono text-xs uppercase tracking-[0.3em] px-2 py-1 bg-sky-blue/10 border-l-2 border-sky-blue">
            02. UNDER THE HOOD
          </span>
        </div>

        <h2
          id="frame-3-headline"
          className="text-3xl md:text-5xl lg:text-6xl font-black text-white uppercase tracking-tight mb-6 max-w-5xl"
        >
          Multi-wave AI analysis.
          <br />
          <span className="text-princeton-orange underline decoration-princeton-orange decoration-4 underline-offset-8">
            Semantic enforcement.
          </span>
        </h2>

        <p className="text-lg md:text-xl text-gray-300 font-mono max-w-3xl mb-16 md:mb-20">
          Archie runs the same analysis a senior architect would — then embeds the
          conclusions where agents work.
        </p>

        {/* Two-column: build phase | enforce phase */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16">
          {/* Build phase — pipeline */}
          <div>
            <div className="mb-6">
              <h3 className="text-2xl md:text-3xl font-black text-sky-blue uppercase tracking-tight border-b-2 border-sky-blue pb-2 inline-block">
                Build phase
              </h3>
              <div className="text-gray-400 font-mono text-xs uppercase tracking-widest mt-2">
                /archie-deep-scan
              </div>
            </div>
            <PipelineDiagram />
          </div>

          {/* Enforce phase — rule card + severity */}
          <div>
            <div className="mb-6">
              <h3 className="text-2xl md:text-3xl font-black text-princeton-orange uppercase tracking-tight border-b-2 border-princeton-orange pb-2 inline-block">
                Enforce phase
              </h3>
              <div className="text-gray-400 font-mono text-xs uppercase tracking-widest mt-2">
                Every agent edit
              </div>
            </div>
            <RuleCard />
            <SeverityLegend />
          </div>
        </div>

        {/* Maintenance loop strip */}
        <div className="mt-16 md:mt-20 border-2 border-neon/40 bg-black/40 px-6 py-5 flex flex-col md:flex-row items-start md:items-center gap-3 md:gap-6">
          <span className="text-neon font-mono text-xs uppercase tracking-[0.3em] flex-shrink-0">
            /archie-scan
          </span>
          <span className="text-gray-300 font-mono text-sm md:text-base">
            Senior-architect pass on the diff. New findings become new rules. The model
            sharpens with every run.
          </span>
          <span className="text-gray-500 font-mono text-[10px] uppercase tracking-widest md:ml-auto flex-shrink-0">
            1-3 min, run often
          </span>
        </div>
      </div>
    </section>
  )
}
