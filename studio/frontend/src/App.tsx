import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { BookOpen, Boxes, Workflow } from 'lucide-react'
import ProductTab from './tabs/ProductTab'
import ArchitectureTab from './tabs/ArchitectureTab'
import WorkflowTab from './tabs/WorkflowTab'

const tabs = [
  { to: '/product', label: 'Product', icon: BookOpen },
  { to: '/architecture', label: 'Architecture', icon: Boxes },
  { to: '/workflow', label: 'Workflow', icon: Workflow },
]

export default function App() {
  return (
    <div className="flex h-screen bg-background text-foreground">
      <nav className="flex w-14 shrink-0 flex-col items-center gap-2 border-r border-border bg-card py-3">
        {tabs.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            title={label}
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
      </nav>
      <main className="min-w-0 flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/product" replace />} />
          <Route path="/product" element={<ProductTab />} />
          <Route path="/architecture/*" element={<ArchitectureTab />} />
          <Route path="/workflow" element={<WorkflowTab />} />
        </Routes>
      </main>
    </div>
  )
}
