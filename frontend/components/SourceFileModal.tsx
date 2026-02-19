import { useState, useEffect, useCallback } from 'react'
import { X } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'

interface SourceFileModalProps {
    filePath: string
    repoId: string
    isOpen: boolean
    onClose: () => void
}

export function SourceFileModal({ filePath, repoId, isOpen, onClose }: SourceFileModalProps) {
    const { token } = useAuth()
    const [content, setContent] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)

    const fetchContent = useCallback(async () => {
        if (!filePath || !repoId || !token) return

        setIsLoading(true)
        setError(null)
        setContent(null)

        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        try {
            const res = await fetch(
                `${API_URL}/api/v1/workspace/repositories/${repoId}/source-files/${filePath}`,
                { headers: { Authorization: `Bearer ${token}` } }
            )
            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                throw new Error(data.detail || `File not available (${res.status})`)
            }
            const data = await res.json()
            setContent(data.content)
        } catch (err: any) {
            setError(err.message || 'Failed to load file')
        } finally {
            setIsLoading(false)
        }
    }, [filePath, repoId, token])

    useEffect(() => {
        if (isOpen) {
            fetchContent()
        }
    }, [isOpen, fetchContent])

    // Close on Escape key
    useEffect(() => {
        if (!isOpen) return
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose()
        }
        document.addEventListener('keydown', handleKeyDown)
        return () => document.removeEventListener('keydown', handleKeyDown)
    }, [isOpen, onClose])

    if (!isOpen) return null

    return (
        <div
            className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center"
            onClick={(e) => {
                if (e.target === e.currentTarget) onClose()
            }}
        >
            <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-[90vw] max-w-4xl max-h-[80vh] flex flex-col">
                <div className="flex justify-between items-center p-4 border-b">
                    <code className="text-sm font-mono text-foreground truncate mr-4">{filePath}</code>
                    <button
                        onClick={onClose}
                        className="flex-shrink-0 p-1 rounded hover:bg-muted transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
                <div className="overflow-auto p-4 flex-1">
                    {isLoading && (
                        <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
                            Loading file content...
                        </div>
                    )}
                    {error && (
                        <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
                            {error}
                        </div>
                    )}
                    {content !== null && (
                        <pre className="text-sm font-mono whitespace-pre overflow-x-auto">{content}</pre>
                    )}
                </div>
            </div>
        </div>
    )
}
