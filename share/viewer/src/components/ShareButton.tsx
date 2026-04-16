import { useState } from 'react'
import { Share2, Copy, Check, Loader2, ExternalLink } from 'lucide-react'
import { isLocalMode } from '@/lib/data'

export function ShareButton() {
  const [state, setState] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle')
  const [shareUrl, setShareUrl] = useState('')
  const [copied, setCopied] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  if (!isLocalMode()) return null

  const handleShare = async () => {
    setState('uploading')
    try {
      const res = await fetch('/api/share', { method: 'POST' })
      if (!res.ok) {
        const data = await res.json().catch(() => ({ error: 'Upload failed' }))
        throw new Error(data.error || 'Upload failed')
      }
      const data = await res.json()
      setShareUrl(data.url)
      setState('done')
    } catch (e: any) {
      setErrorMsg(e.message)
      setState('error')
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(shareUrl).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  if (state === 'done') {
    return (
      <div className="space-y-3">
        <p className="text-xs text-ink/50">Blueprint shared successfully!</p>
        <div className="flex items-center gap-2">
          <input
            readOnly
            value={shareUrl}
            className="flex-1 px-3 py-2 rounded-lg border border-papaya-300 text-xs bg-white truncate"
          />
          <button onClick={handleCopy} className="px-3 py-2 rounded-lg text-xs bg-teal text-white font-bold flex items-center gap-1">
            {copied ? <><Check className="w-3 h-3" /> Copied</> : <><Copy className="w-3 h-3" /> Copy</>}
          </button>
        </div>
        <a
          href={shareUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-teal hover:underline flex items-center gap-1"
        >
          <ExternalLink className="w-3 h-3" /> Open in browser
        </a>
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="space-y-2">
        <p className="text-xs text-brandy">{errorMsg}</p>
        <button onClick={handleShare} className="px-4 py-2 rounded-xl text-xs bg-teal text-white font-bold">
          Try again
        </button>
      </div>
    )
  }

  return (
    <button
      onClick={handleShare}
      disabled={state === 'uploading'}
      className="px-4 py-2 rounded-xl text-sm bg-teal text-white font-bold flex items-center gap-2 hover:bg-teal-600 transition-colors disabled:opacity-50"
    >
      {state === 'uploading' ? (
        <><Loader2 className="w-4 h-4 animate-spin" /> Uploading...</>
      ) : (
        <><Share2 className="w-4 h-4" /> Share Blueprint</>
      )}
    </button>
  )
}
