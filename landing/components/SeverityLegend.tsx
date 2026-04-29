const ROWS = [
  {
    color: "princeton-orange",
    bg: "bg-princeton-orange/10",
    border: "border-princeton-orange/40",
    text: "text-princeton-orange",
    classes: "decision_violation · pitfall_triggered · mechanical_violation",
    action: "Blocks (exit 2)",
  },
  {
    color: "amber-flame",
    bg: "bg-amber-flame/10",
    border: "border-amber-flame/40",
    text: "text-amber-flame",
    classes: "tradeoff_undermined",
    action: "Warns prominently",
  },
  {
    color: "sky-blue",
    bg: "bg-sky-blue/10",
    border: "border-sky-blue/40",
    text: "text-sky-blue",
    classes: "pattern_divergence",
    action: "Informs quietly",
  },
] as const

export function SeverityLegend() {
  return (
    <div className="border-2 border-white/10 bg-black/40 mt-6">
      <div className="bg-white/5 border-b border-white/10 px-4 py-2">
        <span className="text-gray-400 font-mono text-[10px] uppercase tracking-[0.3em]">
          Severity gates
        </span>
      </div>
      <div className="divide-y divide-white/10">
        {ROWS.map((row) => (
          <div
            key={row.color}
            className={`flex items-start gap-4 px-4 py-3 ${row.bg}`}
          >
            <div
              className={`w-2 h-2 rounded-full ${row.text.replace("text-", "bg-")} mt-2 flex-shrink-0`}
              aria-hidden="true"
            />
            <div className="flex-1 min-w-0">
              <div className={`${row.text} font-mono text-xs leading-snug truncate`}>
                {row.classes}
              </div>
            </div>
            <div className={`${row.text} font-black text-xs uppercase tracking-widest whitespace-nowrap`}>
              {row.action}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
