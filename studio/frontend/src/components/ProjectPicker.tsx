import { useCallback, useEffect, useState } from 'react'
import { ArrowUp, Boxes, FileText, Folder, FolderOpen, X } from 'lucide-react'

export interface ProjectInfo {
  root: string | null
  prd_root: string | null
  name: string | null
}

interface FsDir {
  name: string
  path: string
  has_archie: boolean
  has_prd: boolean
}

interface FsList {
  path: string
  parent: string | null
  dirs: FsDir[]
}

async function jsonOrThrow(r: Response) {
  if (!r.ok) throw new Error((await r.json()).error ?? `HTTP ${r.status}`)
  return r.json()
}

export default function ProjectPicker({ onPicked, onCancel }: {
  onPicked: (p: ProjectInfo) => void
  onCancel?: () => void
}) {
  const [listing, setListing] = useState<FsList | null>(null)
  const [pathInput, setPathInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const browse = useCallback((path?: string) => {
    setError(null)
    fetch(`/api/fs/list${path ? `?path=${encodeURIComponent(path)}` : ''}`)
      .then(jsonOrThrow)
      .then((l: FsList) => {
        setListing(l)
        setPathInput(l.path)
      })
      .catch((e) => setError(String(e.message ?? e)))
  }, [])

  useEffect(() => {
    browse()
  }, [browse])

  const open = useCallback((path: string) => {
    setBusy(true)
    setError(null)
    fetch('/api/project', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
      .then(jsonOrThrow)
      .then(onPicked)
      .catch((e) => {
        setError(String(e.message ?? e))
        setBusy(false)
      })
  }, [onPicked])

  return (
    <div className="flex h-screen items-center justify-center bg-background text-foreground">
      <div className="flex h-[34rem] w-[36rem] max-w-[92vw] flex-col rounded-lg border border-border bg-card shadow-sm">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h1 className="text-lg font-semibold">Open a project</h1>
            <p className="text-sm text-muted-foreground">
              Pick the folder of the repository you want to work on.
            </p>
          </div>
          {onCancel && (
            <button onClick={onCancel} aria-label="Cancel" title="Cancel"
              className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground">
              <X size={18} />
            </button>
          )}
        </div>

        <form
          className="flex items-center gap-2 border-b border-border px-5 py-3"
          onSubmit={(e) => {
            e.preventDefault()
            browse(pathInput)
          }}
        >
          <button type="button" onClick={() => listing?.parent && browse(listing.parent)}
            disabled={!listing?.parent} aria-label="Up one folder" title="Up one folder"
            className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40">
            <ArrowUp size={16} />
          </button>
          <input
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            spellCheck={false}
            aria-label="Folder path"
            className="min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-1.5 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-teal"
          />
        </form>

        <div className="min-h-0 flex-1 overflow-auto px-3 py-2">
          {error && (
            <p className="m-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">{error}</p>
          )}
          {!listing && !error && (
            <p className="m-2 text-sm text-muted-foreground">Loading…</p>
          )}
          {listing && listing.dirs.length === 0 && !error && (
            <p className="m-2 text-sm text-muted-foreground">No subfolders here.</p>
          )}
          {listing && (
            <ul className="space-y-0.5">
              {listing.dirs.map((d) => (
                <li key={d.path} className="group flex items-center gap-1">
                  <button onClick={() => browse(d.path)}
                    className="flex min-w-0 flex-1 items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted">
                    <Folder size={15} className="shrink-0 text-muted-foreground" />
                    <span className="truncate">{d.name}</span>
                    {d.has_archie && (
                      <span title="Has .archie data"
                        className="flex items-center gap-1 rounded-full bg-teal/10 px-2 py-0.5 text-xs text-teal">
                        <Boxes size={11} /> archie
                      </span>
                    )}
                    {d.has_prd && (
                      <span title="Has a PRD folder"
                        className="flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        <FileText size={11} /> prd
                      </span>
                    )}
                  </button>
                  <button onClick={() => open(d.path)} disabled={busy}
                    aria-label={`Open ${d.name}`}
                    className="invisible rounded px-2 py-1 text-xs text-teal hover:bg-teal/10 group-hover:visible disabled:opacity-40">
                    Open
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-border px-5 py-3">
          <span className="truncate pr-3 font-mono text-xs text-muted-foreground">{listing?.path ?? ''}</span>
          <button onClick={() => listing && open(listing.path)} disabled={!listing || busy}
            className="flex shrink-0 items-center gap-2 rounded-md bg-teal px-4 py-2 text-sm font-medium text-white hover:bg-teal-600 disabled:opacity-50">
            <FolderOpen size={15} />
            {busy ? 'Opening…' : 'Open this folder'}
          </button>
        </div>
      </div>
    </div>
  )
}
