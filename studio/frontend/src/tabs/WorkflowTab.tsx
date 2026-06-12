import { Workflow } from 'lucide-react'

export default function WorkflowTab() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <Workflow size={40} className="text-muted-foreground" />
      <h2 className="text-lg font-semibold">Workflows</h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        Delivery loops that combine product knowledge and architecture
        knowledge will live here. Nothing to configure yet.
      </p>
    </div>
  )
}
