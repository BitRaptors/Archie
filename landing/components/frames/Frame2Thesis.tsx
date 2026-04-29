import { BookOpen, FolderTree, Shield, TrendingUp } from "lucide-react"
import { PillarCard } from "@/components/PillarCard"

export function Frame2Thesis() {
  return (
    <section
      id="frame-2"
      aria-labelledby="frame-2-headline"
      className="relative py-32 md:py-40 px-4 bg-deep-space-blue overflow-hidden border-t-4 border-neon"
    >
      {/* Vertical watermark */}
      <div
        className="absolute right-0 top-1/2 -translate-y-1/2 opacity-[0.03] text-neon font-black pointer-events-none select-none uppercase z-0"
        style={{ fontSize: "30vh", lineHeight: "1", writingMode: "vertical-rl" }}
        aria-hidden="true"
      >
        Understanding
      </div>

      <div className="max-w-7xl mx-auto relative z-10">
        {/* Section number */}
        <div className="mb-8">
          <span className="inline-block text-neon font-mono text-xs uppercase tracking-[0.3em] px-2 py-1 bg-neon/10 border-l-2 border-neon">
            01. THE THESIS
          </span>
        </div>

        {/* Headline */}
        <h2
          id="frame-2-headline"
          className="text-3xl md:text-5xl lg:text-6xl font-black text-white uppercase tracking-tight mb-6 max-w-5xl"
        >
          Archie builds{" "}
          <span className="text-neon underline decoration-neon decoration-4 underline-offset-8">
            semantic understanding
          </span>{" "}
          of your codebase.
        </h2>

        <p className="text-lg md:text-xl text-gray-300 font-mono max-w-3xl mb-16 md:mb-20">
          Curated knowledge, delivered exactly where and when agents need it.
        </p>

        {/* Hero pillar */}
        <div className="mb-8">
          <PillarCard
            variant="hero"
            accent="neon"
            icon={<Shield className="w-12 h-12" strokeWidth={2} />}
            label="At edit time"
            description="Hooks reject bad edits in real-time, before they land. Not at PR review."
          />
        </div>

        {/* 3 supporting pillars */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
          <PillarCard
            variant="supporting"
            accent="sky-blue"
            icon={<BookOpen className="w-8 h-8" strokeWidth={2} />}
            label="At planning"
            description="Agents read the blueprint and decisions before writing a line."
          />
          <PillarCard
            variant="supporting"
            accent="amber-flame"
            icon={<FolderTree className="w-8 h-8" strokeWidth={2} />}
            label="In context"
            description="Per-folder CLAUDE.md scopes understanding to the file at hand."
          />
          <PillarCard
            variant="supporting"
            accent="princeton-orange"
            icon={<TrendingUp className="w-8 h-8" strokeWidth={2} />}
            label="Over time"
            description="Every scan deepens the model; drift becomes new rules."
          />
        </div>
      </div>
    </section>
  )
}
