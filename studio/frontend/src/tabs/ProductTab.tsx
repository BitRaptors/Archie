import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { BookOpen, ChevronDown, ChevronRight, FileText, FolderPlus, RefreshCw } from 'lucide-react'
import { parseFrontmatter } from '../lib/frontmatter'
import { transformWikilinks, type PrdFileRef } from '../lib/wikilinks'
import FolderBrowser from '../components/FolderBrowser'

interface TreeNode {
  type: 'dir' | 'file'
  name: string
  path: string
  children?: TreeNode[]
}

interface PrdSource {
  root: string
  label: string
  kind: 'explicit' | 'convention' | 'detected'
  tree: TreeNode[]
}

interface PrdTreeResponse {
  sources: PrdSource[]
}

// Selection and wikilink targets use "virtual" paths — `${sourceIndex}/${rel}` —
// so files from multiple PRD sources can't collide on equal relative paths.
function withVirtualPaths(nodes: TreeNode[], prefix: string): TreeNode[] {
  return nodes.map((n) => ({
    ...n,
    path: `${prefix}/${n.path}`,
    children: n.children ? withVirtualPaths(n.children, prefix) : undefined,
  }))
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
          aria-expanded={open}
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
        aria-current={selected === node.path ? 'true' : undefined}
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
  const [sources, setSources] = useState<PrdSource[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [content, setContent] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [treeError, setTreeError] = useState<string | null>(null)
  const [addingFolder, setAddingFolder] = useState(false)
  // Monotonic request id: only the latest loadFile call may commit state, so a
  // slow response for file A can't overwrite file B's content.
  const reqSeq = useRef(0)

  const loadTree = useCallback(() => {
    setTreeError(null)
    fetch('/api/prd/tree')
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error ?? `HTTP ${r.status}`)
        return r.json()
      })
      .then((d: PrdTreeResponse) => setSources(d.sources))
      .catch(() => setTreeError('Could not load the PRD file tree.'))
  }, [])

  useEffect(() => {
    loadTree()
  }, [loadTree])

  // Each source's tree re-keyed with virtual paths (`${index}/${rel}`).
  const virtualTrees = useMemo(
    () => (sources ?? []).map((s, i) => withVirtualPaths(s.tree, String(i))),
    [sources]
  )
  const files = useMemo(() => virtualTrees.flatMap((t) => flattenFiles(t)), [virtualTrees])

  const loadFile = useCallback((virtualPath: string) => {
    const slash = virtualPath.indexOf('/')
    const source = sources?.[Number(virtualPath.slice(0, slash))]
    const rel = virtualPath.slice(slash + 1)
    if (!source) return
    const seq = ++reqSeq.current
    setSelected(virtualPath)
    setContent('')
    setError(null)
    fetch(`/api/prd/file?root=${encodeURIComponent(source.root)}&path=${encodeURIComponent(rel)}`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).error ?? `HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => {
        if (seq === reqSeq.current) setContent(d.content)
      })
      .catch((e) => {
        if (seq === reqSeq.current) setError(String(e.message ?? e))
      })
  }, [sources])

  const addSource = useCallback(async (path: string) => {
    const r = await fetch('/api/prd/source', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
    if (!r.ok) throw new Error((await r.json()).error ?? `HTTP ${r.status}`)
    const d: PrdTreeResponse = await r.json()
    setSources(d.sources)
    setAddingFolder(false)
  }, [])

  // Edits made in Obsidian show up when you tab back to the browser — refresh
  // both the tree (new files) and the open document (changed content).
  useEffect(() => {
    const onFocus = () => {
      loadTree()
      if (selected) loadFile(selected)
    }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [selected, loadFile, loadTree])

  const folderBrowserModal = addingFolder && (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <FolderBrowser
        title="Add a PRD folder"
        subtitle="Pick any folder containing PRD markdown files (inside or outside the project)."
        chooseLabel="Use this folder"
        onChoose={addSource}
        onCancel={() => setAddingFolder(false)}
      />
    </div>
  )

  if (sources && sources.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <BookOpen size={40} className="text-muted-foreground" />
        <h2 className="text-lg font-semibold">No PRD documents found</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          Studio looks for <code>docs/prd/</code>, <code>prd/</code>, and any folder
          with PRD-named markdown files (like <code>spec.prd.md</code>). None matched
          in this project.
        </p>
        <button
          onClick={() => setAddingFolder(true)}
          className="mt-2 flex items-center gap-2 rounded-md bg-teal px-4 py-2 text-sm font-medium text-white hover:bg-teal-600"
        >
          <FolderPlus size={15} /> Choose PRD folder
        </button>
        {folderBrowserModal}
      </div>
    )
  }

  const { data: frontmatter, content: body } = parseFrontmatter(content)
  const transformed = transformWikilinks(body, files)

  return (
    <div className="flex h-full">
      {folderBrowserModal}
      <aside className="w-64 shrink-0 overflow-auto border-r border-border bg-card p-3">
        <div className="mb-2 flex items-center justify-between px-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Product knowledge
          </h2>
          <button
            onClick={() => setAddingFolder(true)}
            title="Add PRD folder"
            aria-label="Add PRD folder"
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <FolderPlus size={14} />
          </button>
        </div>
        {treeError ? (
          <div className="space-y-2 px-2 text-sm">
            <p className="text-muted-foreground">{treeError}</p>
            <button onClick={loadTree} className="flex items-center gap-1 text-teal">
              <RefreshCw size={14} /> Retry
            </button>
          </div>
        ) : sources ? (
          sources.map((s, i) => (
            <div key={s.root} className="mb-3">
              <p
                title={`${s.root} (${s.kind})`}
                className="mb-1 truncate px-2 font-mono text-xs text-muted-foreground"
              >
                {s.label}
              </p>
              <TreeView nodes={virtualTrees[i]} selected={selected} onSelect={loadFile} />
            </div>
          ))
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
                      const raw = href.slice('wikilink:'.length)
                      let target = raw
                      try {
                        target = decodeURIComponent(raw)
                      } catch {
                        // Hand-authored malformed escape (e.g. %zz): keep the raw slice.
                      }
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
