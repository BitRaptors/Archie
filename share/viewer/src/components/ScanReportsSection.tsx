import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { FileText, Calendar } from 'lucide-react'
import { type ScanReport } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  reports: ScanReport[]
}

export function ScanReportsSection({ reports }: Props) {
  const [activeIdx, setActiveIdx] = useState(0)

  if (reports.length === 0) return null

  const active = reports[activeIdx]

  return (
    <div className="flex gap-6 min-h-[400px]">
      {reports.length > 1 && (
        <div className="w-56 shrink-0 space-y-1 overflow-y-auto max-h-[70vh]">
          {reports.map((r, i) => (
            <button
              key={r.filename}
              onClick={() => setActiveIdx(i)}
              className={cn(
                'w-full text-left px-3 py-2 rounded-xl text-xs transition-colors',
                i === activeIdx
                  ? 'bg-teal/10 text-teal font-bold'
                  : 'text-ink/50 hover:text-ink hover:bg-papaya-50'
              )}
            >
              <div className="flex items-center gap-2">
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">{r.filename.replace(/\.md$/, '')}</span>
              </div>
              {r.date && (
                <div className="flex items-center gap-1 mt-0.5 text-[10px] text-ink/30">
                  <Calendar className="w-3 h-3" />
                  <span>{r.date}</span>
                </div>
              )}
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 overflow-y-auto max-h-[70vh] bg-white/60 border border-papaya-400/60 rounded-2xl p-8">
        <div className="prose-archie text-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
            {active.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
