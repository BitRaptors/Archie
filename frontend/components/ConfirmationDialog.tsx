import { useEffect } from 'react'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'

interface ConfirmationDialogProps {
    isOpen: boolean
    onClose: () => void
    onConfirm: () => void
    title: string
    message: string
    confirmText?: string
    cancelText?: string
    destructive?: boolean
    isLoading?: boolean
}

export function ConfirmationDialog({
    isOpen,
    onClose,
    onConfirm,
    title,
    message,
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    destructive = false,
    isLoading = false,
}: ConfirmationDialogProps) {
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
            <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-md mx-4 animate-in fade-in zoom-in-95 duration-200">
                <div className="p-6">
                    {destructive && (
                        <div className={cn("w-12 h-12 rounded-full flex items-center justify-center mb-4", theme.status.errorPanel)}>
                            <AlertTriangle className="w-6 h-6 text-destructive" />
                        </div>
                    )}
                    <h3 className="text-lg font-semibold tracking-tight mb-2">{title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
                </div>
                <div className="flex items-center justify-end gap-3 px-6 pb-6">
                    <Button
                        variant="outline"
                        onClick={onClose}
                        disabled={isLoading}
                    >
                        {cancelText}
                    </Button>
                    <Button
                        variant={destructive ? 'destructive' : 'default'}
                        onClick={onConfirm}
                        disabled={isLoading}
                    >
                        {isLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        {confirmText}
                    </Button>
                </div>
            </div>
        </div>
    )
}
