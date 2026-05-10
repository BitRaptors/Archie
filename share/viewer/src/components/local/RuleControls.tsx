import { useState } from 'react'
import RuleEditModal from './RuleEditModal'

interface Props {
  rule: { id: string; description?: string; why?: string; example?: string; severity_class?: string }
  state: 'active' | 'proposed' | 'ignored'
  onAction: (action: 'adopt' | 'reject' | 'disable' | 'enable') => Promise<void>
  onEdit: (patch: Record<string, string>) => Promise<void>
}

export default function RuleControls({ rule, state, onAction, onEdit }: Props) {
  const [editing, setEditing] = useState(false)
  return (
    <div className="flex gap-2 ml-auto">
      {state === 'proposed' && (
        <>
          <button onClick={() => onAction('adopt')} className="text-tangerine-300 hover:text-tangerine-200" title="Adopt">✓</button>
          <button onClick={() => onAction('reject')} className="text-papaya-400 hover:text-papaya-200" title="Reject">✕</button>
        </>
      )}
      {state === 'active' && (
        <>
          <button onClick={() => setEditing(true)} className="text-papaya-300 hover:text-papaya-100" title="Edit">✎</button>
          <button onClick={() => onAction('disable')} className="text-papaya-400 hover:text-papaya-200" title="Disable">🔒</button>
        </>
      )}
      {state === 'ignored' && (
        <button onClick={() => onAction('enable')} className="text-tangerine-300 hover:text-tangerine-200" title="Enable">🔓</button>
      )}
      {editing && (
        <RuleEditModal
          rule={rule}
          onSave={(patch) => onEdit(patch).finally(() => setEditing(false))}
          onCancel={() => setEditing(false)}
        />
      )}
    </div>
  )
}
