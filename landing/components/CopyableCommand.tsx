"use client"

import { Check, Copy } from "lucide-react"
import { useState } from "react"

type Props = {
  command: string
}

export function CopyableCommand({ command }: Props) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState(false)

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)
      setError(false)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError(true)
      setTimeout(() => setError(false), 3000)
    }
  }

  return (
    <div className="inline-flex flex-col items-stretch gap-2 w-full max-w-2xl">
      <div
        className={[
          "flex items-center gap-4 border-2 border-neon bg-black px-5 py-4 transition-all",
          copied
            ? "shadow-[0_0_30px_rgba(57,255,20,0.7),0_0_60px_rgba(57,255,20,0.4)]"
            : "shadow-[8px_8px_0px_0px_#39ff14]",
        ].join(" ")}
      >
        <span className="text-neon font-mono text-base md:text-lg select-all flex-1 truncate">
          {command}
        </span>
        <button
          onClick={onCopy}
          aria-label={copied ? "Copied to clipboard" : "Copy command"}
          className={[
            "flex items-center gap-2 px-3 py-1.5 font-mono text-xs uppercase tracking-widest font-bold",
            "border border-neon transition-colors",
            copied
              ? "bg-neon text-black"
              : "bg-deep-space-blue text-neon hover:bg-neon hover:text-black",
          ].join(" ")}
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5" /> Copied
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" /> Copy
            </>
          )}
        </button>
      </div>
      {error && (
        <div role="alert" className="text-amber-flame font-mono text-xs uppercase tracking-widest">
          Copy failed — select and ⌘C
        </div>
      )}
    </div>
  )
}
