import LocalPage from '@/pages/LocalPage'

// The full archie-viewer local inspector, mounted as a studio tab. LocalPage
// has no router dependencies and fetches relative /api/* paths, which resolve
// against the studio server's inherited viewer endpoints.
//
// Layout shim: the viewer was built to own the whole viewport — its sidebar
// (and the loading skeleton) use `fixed inset-y-0 left-0`, which pins them to
// the viewport edge and covers the studio's 3.5rem icon rail, making the rail
// unclickable on this tab. The scoped rules below shift the viewer's fixed
// chrome right by the rail width on lg+ screens and widen the content margin
// to match (18rem sidebar + 3.5rem rail). Below lg the viewer's slide-out
// sidebar is a temporary overlay, so it may cover the rail like any modal.
//
// The margin rule targets `main.min-h-screen` — the viewer's LAYOUT main
// (ReportPage.tsx) — and must not match the NESTED <main ml-3> elements the
// Files browsers (GeneratedFilesBrowser/FolderClaudeMdsBrowser) render inside
// it, or their content gets shoved 21.5rem right too.
//
// Known transient gap: the loading skeleton's content sibling is a div with
// lg:ml-64 (not a main), so during loading it underlaps the shifted skeleton
// sidebar by 3.5rem. Accepted — it only lasts until the bundle arrives.
const railShim = `
@media (min-width: 1024px) {
  .studio-arch-tab aside.fixed,
  .studio-arch-tab .fixed.inset-y-0 { left: 3.5rem; }
  .studio-arch-tab main.min-h-screen { margin-left: 21.5rem; }
}
`

export default function ArchitectureTab() {
  return (
    <div className="studio-arch-tab">
      <style>{railShim}</style>
      <LocalPage />
    </div>
  )
}
