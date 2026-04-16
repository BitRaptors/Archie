import { useState, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { ChevronRight, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Props {
  generatedFiles?: Record<string, string>
  folderClaudeMds?: Record<string, string>
}

interface TreeNode {
  [key: string]: TreeNode | { _file: string }
}

function buildTree(keys: string[]): TreeNode {
  const tree: TreeNode = {}
  keys.forEach(key => {
    const parts = key.replace(/\/CLAUDE\.md$/, '').split('/')
    let current = tree
    parts.forEach((part, i) => {
      if (!current[part]) current[part] = {}
      if (i === parts.length - 1) {
        ;(current[part] as any)._file = key
      } else {
        current = current[part] as TreeNode
      }
    })
  })
  return tree
}

function TreeView({
  node,
  depth,
  activeFile,
  onSelect,
}: {
  node: TreeNode
  depth: number
  activeFile: string | null
  onSelect: (key: string) => void
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const keys = Object.keys(node)
    .filter(k => k !== '_file')
    .sort()

  return (
    <>
      {keys.map(k => {
        const child = node[k] as any
        const childKeys = Object.keys(child).filter(ck => ck !== '_file')
        const isLeaf = child._file && childKeys.length === 0
        const isOpen = expanded[k] ?? false

        if (isLeaf) {
          return (
            <button
              key={k}
              onClick={() => onSelect(child._file)}
              className={cn(
                'w-full text-left px-3 py-1.5 rounded-lg text-xs transition-colors',
                depth > 0 && 'ml-3',
                activeFile === child._file
                  ? 'bg-teal/10 text-teal font-bold'
                  : 'text-ink/50 hover:text-ink hover:bg-papaya-50'
              )}
            >
              {k}/CLAUDE.md
            </button>
          )
        }

        return (
          <div key={k} className={cn(depth > 0 && 'ml-3')}>
            <button
              onClick={() => setExpanded(prev => ({ ...prev, [k]: !prev[k] }))}
              className="w-full flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-ink/40 hover:text-ink cursor-pointer"
            >
              <ChevronRight
                className={cn(
                  'w-3 h-3 transition-transform duration-200',
                  isOpen && 'rotate-90'
                )}
              />
              <span>{k}</span>
            </button>
            {isOpen && (
              <div>
                {child._file && (
                  <button
                    onClick={() => onSelect(child._file)}
                    className={cn(
                      'w-full text-left px-3 py-1.5 ml-3 rounded-lg text-xs transition-colors',
                      activeFile === child._file
                        ? 'bg-teal/10 text-teal font-bold'
                        : 'text-ink/50 hover:text-ink hover:bg-papaya-50'
                    )}
                  >
                    CLAUDE.md
                  </button>
                )}
                <TreeView
                  node={child}
                  depth={depth + 1}
                  activeFile={activeFile}
                  onSelect={onSelect}
                />
              </div>
            )}
          </div>
        )
      })}
    </>
  )
}

export function FilesSection({ generatedFiles, folderClaudeMds }: Props) {
  const [activeFile, setActiveFile] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const allFiles = useMemo(() => {
    const files: Record<string, string> = {}
    if (generatedFiles) Object.assign(files, generatedFiles)
    if (folderClaudeMds) Object.assign(files, folderClaudeMds)
    return files
  }, [generatedFiles, folderClaudeMds])

  const rootFiles = useMemo(
    () => Object.keys(generatedFiles || {}).filter(k => !k.includes('/')).sort(),
    [generatedFiles]
  )
  const ruleFiles = useMemo(
    () => Object.keys(generatedFiles || {}).filter(k => k.startsWith('.claude/rules/')).sort(),
    [generatedFiles]
  )
  const fmKeys = useMemo(() => Object.keys(folderClaudeMds || {}).sort(), [folderClaudeMds])
  const tree = useMemo(() => buildTree(fmKeys), [fmKeys])

  const content = activeFile ? allFiles[activeFile] || '' : ''

  const handleCopy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="flex gap-6 min-h-[400px]">
      <div className="w-56 shrink-0 overflow-y-auto max-h-[70vh] space-y-4">
        {rootFiles.length > 0 && (
          <div>
            <p className="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-2">
              Root Files
            </p>
            {rootFiles.map(k => (
              <button
                key={k}
                onClick={() => setActiveFile(k)}
                className={cn(
                  'w-full text-left px-3 py-1.5 rounded-lg text-xs transition-colors',
                  activeFile === k
                    ? 'bg-teal/10 text-teal font-bold'
                    : 'text-ink/50 hover:text-ink hover:bg-papaya-50'
                )}
              >
                {k}
              </button>
            ))}
          </div>
        )}
        {ruleFiles.length > 0 && (
          <div>
            <p className="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-2">
              Rule Files
            </p>
            {ruleFiles.map(k => (
              <button
                key={k}
                onClick={() => setActiveFile(k)}
                className={cn(
                  'w-full text-left px-3 py-1.5 rounded-lg text-xs transition-colors',
                  activeFile === k
                    ? 'bg-teal/10 text-teal font-bold'
                    : 'text-ink/50 hover:text-ink hover:bg-papaya-50'
                )}
              >
                {k.split('/').pop()}
              </button>
            ))}
          </div>
        )}
        {fmKeys.length > 0 && (
          <div>
            <p className="text-[11px] font-black text-ink/30 uppercase tracking-[0.15em] px-3 mb-2">
              Per-Folder CLAUDE.md
            </p>
            <TreeView node={tree} depth={0} activeFile={activeFile} onSelect={setActiveFile} />
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto max-h-[70vh] bg-white/60 border border-papaya-400/60 rounded-2xl p-8">
        {activeFile ? (
          <>
            <div className="flex items-center justify-between mb-6">
              <code className="text-[10px] text-ink/40">{activeFile}</code>
              <button
                onClick={handleCopy}
                className="px-3 py-1 rounded-lg border border-papaya-400/60 text-[10px] text-ink/40 hover:text-ink hover:border-teal transition-colors flex items-center gap-1"
              >
                {copied ? <><Check className="w-3 h-3" /> Copied!</> : <><Copy className="w-3 h-3" /> Copy</>}
              </button>
            </div>
            <div className="prose-archie text-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {content}
              </ReactMarkdown>
            </div>
          </>
        ) : (
          <p className="text-ink/40">Select a file...</p>
        )}
      </div>
    </div>
  )
}
