import { useCallback, useEffect, useMemo, useState } from 'react'
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { BookOpen, ChevronDown, ChevronRight, FileText, RefreshCw } from 'lucide-react'
import { parseFrontmatter } from '../lib/frontmatter'
import { transformWikilinks, type PrdFileRef } from '../lib/wikilinks'

interface TreeNode {
  type: 'dir' | 'file'
  name: string
  path: string
  children?: TreeNode[]
}

interface PrdTreeResponse {
  prd_root: string | null
  tree: TreeNode[]
}

function flattenFiles(nodes: TreeNode[]): PrdFileRef[] {
  return nodes.flatMap((n) =>
    n.type === 'file' ? [{ name: n.name, path: n.path }] : flattenFiles(n.children ?? [])
  )
}

function TreeView({ nodes, selected, onSelect }: {
  nodes: TreeNode[]
  selected: string | null
  onSelect: (path: string) => void
}) {
  return (
    <ul className="space-y-0.5">
      {nodes.map((n) => (
        <TreeEntry key={n.path} node={n} selected={selected} onSelect={onSelect} />
      ))}
    </ul>
  )
}

function TreeEntry({ node, selected, onSelect }: {
  node: TreeNode
  selected: string | null
  onSelect: (path: string) => void
}) {
  const [open, setOpen] = useState(true)
  if (node.type === 'dir') {
    return (
      <li>
        <button
          onClick={() => setOpen(!open)}
          className="flex w-full items-center gap-1 rounded px-2 py-1 text-sm font-medium text-muted-foreground hover:bg-muted"
        >
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {node.name}
        </button>
        {open && node.children && (
          <div className="ml-3 border-l border-border pl-1">
            <TreeView nodes={node.children} selected={selected} onSelect={onSelect} />
          </div>
        )}
      </li>
    )
  }
  return (
    <li>
      <button
        onClick={() => onSelect(node.path)}
        className={`flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-sm ${
          selected === node.path ? 'bg-teal/10 text-teal' : 'hover:bg-muted'
        }`}
      >
        <FileText size={14} className="shrink-0" />
        {node.name.replace(/\.md$/, '')}
      </button>
    </li>
  )
}

export default function ProductTab() {
  const [tree, setTree] = useState<PrdTreeResponse | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [content, setContent] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/prd/tree')
      .then((r) => r.json())
      .then(setTree)
      .catch(() => setError('Could not load the PRD file tree.'))
  }, [])

  const files = useMemo(() => (tree ? flattenFiles(tree.tree) : []), [tree])

  const loadFile = useCallback((path: string) => {
    setSelected(path)
    setError(null)
    fetch(`/api/prd/file?path=${encodeURIComponent(path)}`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error ?? `HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => setContent(d.content))
      .catch((e) => setError(String(e.message ?? e)))
  }, [])

  // Edits made in Obsidian show up when you tab back to the browser.
  useEffect(() => {
    const onFocus = () => {
      if (selected) loadFile(selected)
    }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [selected, loadFile])

  if (tree && tree.prd_root === null) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <BookOpen size={40} className="text-muted-foreground" />
        <h2 className="text-lg font-semibold">No PRD folder found</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          Put your PRD markdown files in <code>docs/prd/</code> (or <code>prd/</code>)
          inside the project, or launch with <code>--prd path/to/folder</code>.
        </p>
      </div>
    )
  }

  const { data: frontmatter, content: body } = parseFrontmatter(content)
  const transformed = transformWikilinks(body, files)

  return (
    <div className="flex h-full">
      <aside className="w-64 shrink-0 overflow-auto border-r border-border bg-card p-3">
        <h2 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Product knowledge
        </h2>
        {tree ? (
          <TreeView nodes={tree.tree} selected={selected} onSelect={loadFile} />
        ) : (
          <p className="px-2 text-sm text-muted-foreground">Loading…</p>
        )}
      </aside>
      <section className="min-w-0 flex-1 overflow-auto">
        {error && (
          <div className="m-6 flex items-center gap-3 rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm">
            <span>{error}</span>
            {selected && (
              <button onClick={() => loadFile(selected)} className="flex items-center gap-1 text-teal">
                <RefreshCw size={14} /> Retry
              </button>
            )}
          </div>
        )}
        {!error && !selected && (
          <p className="m-8 text-sm text-muted-foreground">Select a document on the left.</p>
        )}
        {!error && selected && (
          <article className="mx-auto max-w-3xl p-8">
            {Object.keys(frontmatter).length > 0 && (
              <div className="mb-6 flex flex-wrap gap-2 border-b border-border pb-4">
                {Object.entries(frontmatter).map(([k, v]) => (
                  <span key={k} className="rounded-full bg-muted px-3 py-1 text-xs">
                    <span className="font-semibold">{k}:</span> {v}
                  </span>
                ))}
              </div>
            )}
            <div className="prose max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                // react-markdown's default sanitizer strips unknown URL schemes;
                // let our wikilink:/unresolved: markers through to the renderer.
                urlTransform={(url) =>
                  url.startsWith('wikilink:') || url.startsWith('unresolved:')
                    ? url
                    : defaultUrlTransform(url)
                }
                components={{
                  a: ({ node: _node, href, children, ...props }) => {
                    if (href?.startsWith('wikilink:')) {
                      const target = decodeURIComponent(href.slice('wikilink:'.length))
                      return (
                        <a
                          {...props}
                          href={`#${target}`}
                          onClick={(e) => {
                            e.preventDefault()
                            loadFile(target)
                          }}
                        >
                          {children}
                        </a>
                      )
                    }
                    if (href?.startsWith('unresolved:')) {
                      return (
                        <span className="cursor-not-allowed text-muted-foreground underline decoration-dotted">
                          {children}
                        </span>
                      )
                    }
                    return (
                      <a href={href} target="_blank" rel="noreferrer" {...props}>
                        {children}
                      </a>
                    )
                  },
                }}
              >
                {transformed}
              </ReactMarkdown>
            </div>
          </article>
        )}
      </section>
    </div>
  )
}
