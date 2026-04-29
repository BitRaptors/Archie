import { Construction } from "lucide-react"

// Frame 4 is intentionally a placeholder. Real artifacts (hook rejection,
// per-folder CLAUDE.md, scan_report.md) land in a follow-up PR once Gabor
// reviews the layout and provides final content. See TODOS.md.

export function Frame4Receipts() {
  return (
    <section
      id="frame-4"
      aria-labelledby="frame-4-headline"
      className="relative py-20 md:py-28 px-4 bg-black overflow-hidden border-t-4 border-blue-green"
    >
      <div className="absolute top-0 right-0 w-[50%] h-full bg-[radial-gradient(circle_at_70%_50%,#023047_0%,transparent_70%)] opacity-30 pointer-events-none" />

      {/* Vertical watermark */}
      <div
        className="absolute -left-10 top-1/2 -translate-y-1/2 opacity-[0.03] text-blue-green font-black pointer-events-none select-none uppercase z-0"
        style={{ fontSize: "30vh", lineHeight: "1", writingMode: "vertical-rl" }}
        aria-hidden="true"
      >
        Output
      </div>

      <div className="max-w-7xl mx-auto relative z-10">
        <div className="mb-8">
          <span className="inline-block text-blue-green font-mono text-xs uppercase tracking-[0.3em] px-2 py-1 bg-blue-green/10 border-l-2 border-blue-green">
            03. RECEIPTS
          </span>
        </div>

        <h2
          id="frame-4-headline"
          className="text-3xl md:text-4xl lg:text-5xl font-black text-white uppercase tracking-tight mb-4 max-w-5xl"
        >
          This is what semantic
          <br />
          <span className="text-blue-green underline decoration-blue-green decoration-4 underline-offset-8">
            understanding looks like.
          </span>
        </h2>

        <p className="text-base md:text-lg text-gray-300 font-mono max-w-3xl mb-12">
          No marketing screenshots. Real output from real codebases.
        </p>

        {/* Placeholder block — three artifacts coming later */}
        <div className="border-2 border-dashed border-blue-green/40 bg-deep-space-blue-100/40 px-8 py-16 flex flex-col items-center text-center">
          <Construction className="w-12 h-12 text-blue-green mb-6" />
          <div className="text-blue-green font-mono text-xs uppercase tracking-[0.3em] mb-4">
            Coming soon
          </div>
          <h3 className="text-2xl md:text-3xl font-black text-white uppercase tracking-tight mb-4 max-w-2xl">
            Three real artifacts: hook rejection, per-folder CLAUDE.md, scan report
          </h3>
          <p className="text-gray-300 font-mono text-sm md:text-base max-w-2xl mb-6">
            Real Archie output from a public repo, with a modal viewer for the full
            files. We&apos;re finalizing the content — see Frame 5 in the meantime to
            install Archie and run it on your own codebase.
          </p>
          <a
            href="#frame-5"
            className="text-blue-green font-mono text-xs uppercase tracking-[0.3em] hover:text-neon transition-colors border-b border-blue-green hover:border-neon pb-1"
          >
            Skip to install ↓
          </a>
        </div>
      </div>
    </section>
  )
}
