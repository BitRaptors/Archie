interface Props { count: number }

export default function IntentLayerEmptyState({ count }: Props) {
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="bg-ink-900/50 border border-ink-700 rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-3">📁 Per-folder context not yet generated</h2>
        <p className="text-papaya-200 mb-4">
          Archie can write a CLAUDE.md into each meaningful directory of your repo,
          giving AI agents directory-level architectural context (what this layer
          does, what it depends on, what to avoid here). Without this, agents only
          see the root CLAUDE.md.
        </p>
        <p className="text-papaya-200 mb-2 font-semibold">Two ways to generate:</p>
        <ul className="list-none space-y-3 mb-4">
          <li>
            <code className="text-tangerine-300">/archie-deep-scan</code>
            <p className="text-papaya-300 text-sm ml-4">
              Runs the intent layer as Phase 7. Full baseline, ~15-20 min.
            </p>
          </li>
          <li>
            <code className="text-tangerine-300">/archie-intent-layer prepare</code>
            <span className="text-papaya-300"> &amp;&amp; </span>
            <code className="text-tangerine-300">/archie-intent-layer next-ready</code>
            <p className="text-papaya-300 text-sm ml-4">
              Incremental, resumable across sessions. Run next-ready until the queue is empty.
            </p>
          </li>
        </ul>
        <p className="text-papaya-400 text-sm">
          Detected: {count} per-folder CLAUDE.md file{count === 1 ? '' : 's'} outside the repo root.
        </p>
      </div>
    </div>
  )
}
