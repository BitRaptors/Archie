import { ArrowUpRight } from "lucide-react"

const BLUEPRINT_URL =
  "https://archie-viewer.vercel.app/r/L6HpGRwKFcSq80Gra32neJy0/details"

export function Frame4Receipts() {
  return (
    <section
      id="frame-4"
      aria-labelledby="frame-4-headline"
      className="relative min-h-screen flex flex-col justify-center py-16 md:py-20 px-4 bg-black overflow-hidden border-t-4 border-blue-green"
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

      <div className="max-w-7xl mx-auto relative z-10 w-full">
        <div className="mb-8 md:mb-10">
          <span className="inline-block text-blue-green font-mono text-xs uppercase tracking-[0.3em] px-2 py-1 bg-blue-green/10 border-l-2 border-blue-green mb-4">
            03. RECEIPTS
          </span>
          <h2
            id="frame-4-headline"
            className="text-3xl md:text-4xl lg:text-5xl font-black text-white uppercase tracking-tight mb-3 max-w-5xl"
          >
            This is what semantic{" "}
            <span className="text-blue-green underline decoration-blue-green decoration-4 underline-offset-8">
              understanding looks like.
            </span>
          </h2>
          <p className="text-base md:text-lg text-gray-300 font-mono max-w-3xl">
            A real Archie blueprint, embedded below. Click to open the live, navigable
            viewer.
          </p>
        </div>

        {/* Static preview card — full container width so desktop visitors get the
            desktop blueprint layout; iframe naturally adapts to mobile width */}
        <a
          href={BLUEPRINT_URL}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Open the live Archie blueprint in a new tab"
          className="group block w-full border-2 border-blue-green shadow-[8px_8px_0px_0px_#219ebc] hover:shadow-[12px_12px_0px_0px_#39ff14] hover:border-neon hover:-translate-x-1 hover:-translate-y-1 transition-all bg-black cursor-pointer"
        >
          {/* Static iframe preview — fixed height, not full viewport */}
          <div className="relative h-[440px] md:h-[560px] overflow-hidden">
            <iframe
              src={BLUEPRINT_URL}
              title="Archie blueprint preview"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
              tabIndex={-1}
              aria-hidden="true"
              scrolling="no"
              className="absolute inset-0 w-full h-full bg-white pointer-events-none select-none"
            />

            {/* Hover overlay */}
            <div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/40 transition-colors duration-300">
              <span className="opacity-0 group-hover:opacity-100 translate-y-2 group-hover:translate-y-0 transition-all duration-300 inline-flex items-center gap-3 bg-neon text-black px-6 py-3 font-black text-sm uppercase tracking-widest border-2 border-black shadow-[6px_6px_0px_0px_rgba(0,0,0,0.8)]">
                Open the blueprint
                <ArrowUpRight className="w-4 h-4" />
              </span>
            </div>
          </div>
        </a>
      </div>
    </section>
  )
}
