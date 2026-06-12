import FolderBrowser from './FolderBrowser'

export interface ProjectInfo {
  root: string | null
  prd_root: string | null
  name: string | null
}

export default function ProjectPicker({ onPicked, onCancel }: {
  onPicked: (p: ProjectInfo) => void
  onCancel?: () => void
}) {
  return (
    <div className="flex h-screen items-center justify-center bg-background text-foreground">
      <FolderBrowser
        title="Open a project"
        subtitle="Pick the folder of the repository you want to work on."
        chooseLabel="Open this folder"
        onCancel={onCancel}
        onChoose={async (path) => {
          const r = await fetch('/api/project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
          })
          if (!r.ok) throw new Error((await r.json()).error ?? `HTTP ${r.status}`)
          onPicked(await r.json())
        }}
      />
    </div>
  )
}
