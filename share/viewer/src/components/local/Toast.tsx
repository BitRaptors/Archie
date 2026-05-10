import { useEffect } from 'react'

interface Props {
  message: string | null
  onDismiss: () => void
}

export default function Toast({ message, onDismiss }: Props) {
  useEffect(() => {
    if (!message) return
    const id = setTimeout(onDismiss, 2000)
    return () => clearTimeout(id)
  }, [message, onDismiss])

  if (!message) return null
  return (
    <div className="fixed bottom-4 right-4 bg-papaya-700/90 text-ink-900 px-4 py-2 rounded shadow-lg z-50">
      {message}
    </div>
  )
}
