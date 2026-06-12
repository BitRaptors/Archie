import { useEffect, useState } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { BookOpen, Boxes, FolderOpen, Workflow } from 'lucide-react'
import ProductTab from './tabs/ProductTab'
import ArchitectureTab from './tabs/ArchitectureTab'
import WorkflowTab from './tabs/WorkflowTab'
import ProjectPicker, { type ProjectInfo } from './components/ProjectPicker'

const tabs = [
  { to: '/product', label: 'Product', icon: BookOpen },
  { to: '/architecture', label: 'Architecture', icon: Boxes },
  { to: '/workflow', label: 'Workflow', icon: Workflow },
]

export default function App() {
  const [project, setProject] = useState<ProjectInfo | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [picking, setPicking] = useState(false)

  useEffect(() => {
    fetch('/api/project')
      .then((r) => r.json())
      .then((p: ProjectInfo) => setProject(p.root ? p : null))
      .catch(() => setProject(null))
      .finally(() => setLoaded(true))
  }, [])

  if (!loaded) return null
  if (!project || picking) {
    return (
      <ProjectPicker
        onPicked={(p) => {
          setProject(p)
          setPicking(false)
        }}
        onCancel={project ? () => setPicking(false) : undefined}
      />
    )
  }

  return (
    <div className="flex h-screen bg-background text-foreground">
      <nav className="flex w-14 shrink-0 flex-col items-center gap-2 border-r border-border bg-card py-3">
        {tabs.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            title={label}
            aria-label={label}
            className={({ isActive }) =>
              `flex h-10 w-10 items-center justify-center rounded-md transition-colors ${
                isActive
                  ? 'bg-teal text-white'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              }`
            }
          >
            <Icon size={20} />
          </NavLink>
        ))}
        <button
          onClick={() => setPicking(true)}
          title={`Switch project (current: ${project.name})`}
          aria-label="Switch project"
          className="mt-auto flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <FolderOpen size={18} />
        </button>
      </nav>
      {/* key remounts the tabs when the project changes so they refetch */}
      <main key={project.root ?? ''} className="min-w-0 flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/product" replace />} />
          <Route path="/product" element={<ProductTab />} />
          <Route path="/architecture/*" element={<ArchitectureTab />} />
          <Route path="/workflow" element={<WorkflowTab />} />
          <Route path="*" element={<Navigate to="/product" replace />} />
        </Routes>
      </main>
    </div>
  )
}
