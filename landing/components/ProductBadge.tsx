export function ProductBadge() {
  return (
    <div className="inline-flex items-center gap-3 mb-8 px-3 py-1.5 border-l-2 border-neon">
      <span className="w-2 h-2 bg-neon rounded-full animate-pulse" aria-hidden="true" />
      <span className="text-sky-blue font-mono text-xs uppercase tracking-[0.3em]">
        Archie · architecture analysis for AI agents
      </span>
    </div>
  )
}
