import { useState, useEffect, useCallback } from 'react'
import { X, FileCode, Check, Copy, Loader2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/cjs/styles/prism'
import { theme } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

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
    const [copied, setCopied] = useState(false)

    const fetchContent = useCallback(async () => {
        if (!filePath || !repoId || !token) return

        setIsLoading(true)
        setError(null)
        setContent(null)

        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        try {
            const res = await fetch(
                `${API_URL}/api/v1/workspace/repositories/${repoId}/source-files/${encodeURIComponent(filePath)}`,
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

    useEffect(() => {
        if (!isOpen) return
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose()
        }
        document.addEventListener('keydown', handleKeyDown)
        return () => document.removeEventListener('keydown', handleKeyDown)
    }, [isOpen, onClose])

    const handleCopy = () => {
        if (!content) return
        navigator.clipboard.writeText(content)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    if (!isOpen) return null

    const fileExtension = filePath.split('.').pop() || 'typescript'

    return (
        <div
            className="fixed inset-0 z-[200] flex items-center justify-center p-4 lg:p-12"
            onClick={(e) => {
                if (e.target === e.currentTarget) onClose()
            }}
        >
            <div className="absolute inset-0 bg-ink/60 backdrop-blur-md animate-in fade-in duration-300" />

            <div className="relative w-full max-w-6xl h-full flex flex-col bg-white/90 backdrop-blur-xl rounded-[2.5rem] shadow-2xl border border-white/20 overflow-hidden animate-in zoom-in-95 duration-500">
                {/* Header */}
                <div className="flex items-center justify-between px-8 py-6 border-b border-papaya-300/60 bg-white/40">
                    <div className="flex items-center gap-4 group">
                        <div className="p-3 rounded-2xl bg-teal/10 shadow-inner group-hover:bg-teal/20 transition-all">
                            <FileCode className="w-6 h-6 text-teal" />
                        </div>
                        <div className="overflow-hidden">
                            <h3 className="text-lg font-black text-ink truncate leading-tight">{filePath.split('/').pop()}</h3>
                            <div className="flex items-center gap-2 mt-1">
                                <span className="text-[10px] font-black uppercase tracking-widest text-ink/30 px-2 py-0.5 bg-ink/5 rounded-md">{repoId}</span>
                                <span className="text-[10px] text-ink/40 font-mono truncate">{filePath}</span>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        {content && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleCopy}
                                className="h-10 rounded-xl border-papaya-400/60 hover:bg-white transition-all gap-2"
                            >
                                {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                                <span className="text-xs font-bold">{copied ? "Copied" : "Copy Code"}</span>
                            </Button>
                        )}
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={onClose}
                            className="w-10 h-10 rounded-xl hover:bg-brandy/10 hover:text-brandy text-ink/40"
                        >
                            <X className="w-5 h-5" />
                        </Button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-hidden bg-[#1e1e1e] relative flex flex-col">
                    {isLoading && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[#1e1e1e]/80 backdrop-blur-sm z-10 animate-in fade-in duration-300">
                            <Loader2 className="w-12 h-12 animate-spin text-teal shadow-teal/20" />
                            <p className="text-sm font-black uppercase tracking-[0.2em] text-white/20">Streaming Source Code</p>
                        </div>
                    )}

                    {error && (
                        <div className="flex-1 flex flex-col items-center justify-center py-24 text-center bg-white">
                            <div className="w-16 h-16 bg-brandy/10 rounded-full flex items-center justify-center mb-6">
                                <X className="w-8 h-8 text-brandy" />
                            </div>
                            <h3 className="text-xl font-bold text-ink mb-2">Failed to load source</h3>
                            <p className="text-sm text-ink-300 max-w-xs">{error}</p>
                            <Button onClick={fetchContent} className={cn("mt-8", theme.interactive.cta)}>Try Again</Button>
                        </div>
                    )}

                    {content !== null && (
                        <div className="flex-1 overflow-auto">
                            <SyntaxHighlighter
                                language={fileExtension === 'tsx' ? 'typescript' : (fileExtension === 'py' ? 'python' : fileExtension)}
                                style={vscDarkPlus}
                                customStyle={{
                                    margin: 0,
                                    padding: '2.5rem',
                                    fontSize: '13px',
                                    lineHeight: '1.7',
                                    backgroundColor: 'transparent',
                                    minHeight: '100%'
                                }}
                                codeTagProps={{
                                    className: "font-mono"
                                }}
                                showLineNumbers={true}
                                lineNumberStyle={{
                                    minWidth: '3.5em',
                                    paddingRight: '1.5em',
                                    color: '#444',
                                    textAlign: 'right',
                                    userSelect: 'none',
                                    borderRight: '1px solid #333',
                                    marginRight: '1.5em'
                                }}
                            >
                                {content}
                            </SyntaxHighlighter>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="px-8 py-4 border-t border-papaya-300/60 bg-white/40 flex justify-between items-center shrink-0">
                    <div className="flex items-center gap-4 text-[10px] font-black uppercase tracking-widest text-ink/30">
                        <div className="flex items-center gap-1.5">
                            <div className="w-1.5 h-1.5 rounded-full bg-teal" />
                            <span>Read Only Source</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <div className="w-1.5 h-1.5 rounded-full bg-tangerine" />
                            <span>Analyzed</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
