import { ArrowUpRight } from "lucide-react"

export function StatBlock() {
  return (
    <div className="border-4 border-blue-green bg-black p-8 shadow-[8px_8px_0px_0px_#219ebc] flex flex-col gap-10">
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <span className="text-6xl font-black text-amber-flame leading-none tracking-tighter">
            65%
          </span>
          <p className="text-lg text-white font-black uppercase tracking-tight leading-tight">
            say AI misses context
            <br />
            during refactoring.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-6xl font-black text-amber-flame leading-none tracking-tighter">
            44%
          </span>
          <p className="text-lg text-white font-black uppercase tracking-tight leading-tight">
            blame context gaps
            <br />
            for quality degradation.
          </p>
        </div>
      </div>

      <a
        href="https://www.qodo.ai/reports/state-of-ai-code-quality/"
        target="_blank"
        rel="noopener noreferrer"
        className="group block pt-6 border-t border-white/10"
      >
        <div className="text-princeton-orange text-xl font-black uppercase leading-tight group-hover:text-neon transition-all flex items-start gap-3">
          <span className="flex-1">Not hallucinations. Not model capability. Context.</span>
          <ArrowUpRight className="w-6 h-6 flex-shrink-0 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
        </div>
        <div className="mt-3 text-gray-400 text-[10px] font-black uppercase tracking-[0.3em] flex items-center gap-2 group-hover:text-gray-300 transition-colors">
          <div className="w-8 h-px bg-gray-500" />
          Source: State of AI Code Quality, 2025
        </div>
      </a>
    </div>
  )
}
