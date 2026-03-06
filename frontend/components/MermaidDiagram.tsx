'use client'

import React, { useEffect, useRef, useState } from 'react'

interface MermaidDiagramProps {
  chart: string
}

export function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function render() {
      try {
        const mermaid = (await import('mermaid')).default
        mermaid.initialize({
          startOnLoad: false,
          theme: 'base',
          themeVariables: {
            background: 'transparent',
            primaryColor: '#CEEEF6',
            primaryTextColor: '#023047',
            primaryBorderColor: '#219EBC',
            lineColor: '#219EBC',
            secondaryColor: '#FFB703',
            tertiaryColor: '#FB8500',
            fontFamily: 'ui-sans-serif, system-ui, sans-serif',
            fontSize: '14px',
          },
          securityLevel: 'loose',
          suppressErrorUI: true,
        })

        const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

        let cleanChart = chart.trim()
        if (!cleanChart) return

        // Heuristic: If we see something like [Text / More], wrap in quotes: ["Text / More"]
        cleanChart = cleanChart.replace(/\[([^\]]*\/[^\]]*)\]/g, '["$1"]')

        try {
          const { svg: rendered } = await mermaid.render(id, cleanChart)
          if (!cancelled) {
            setSvg(rendered)
            setError(null)
          }
        } catch (renderErr: any) {
          // Retry with original chart if quoted one failed
          try {
            const { svg: rendered } = await mermaid.render(id + '-retry', chart.trim())
            if (!cancelled) {
              setSvg(rendered)
              setError(null)
            }
          } catch (innerErr: any) {
            throw innerErr
          }
        }
      } catch (err: any) {
        if (!cancelled) {
          console.error('Mermaid render error:', err)
          setError(err.message || 'Failed to render diagram')
          setSvg('')
        }
      }
    }

    render()
    return () => { cancelled = true }
  }, [chart])

  if (error) {
    return (
      <div className="border border-amber-200 bg-amber-50 rounded-lg p-4 my-4">
        <p className="text-xs text-amber-700 font-medium mb-2">Diagram render error</p>
        <pre className="text-xs text-amber-900 font-mono whitespace-pre-wrap overflow-x-auto truncate max-h-40">{chart}</pre>
      </div>
    )
  }

  if (!svg) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground text-sm font-medium">
        Rendering diagram...
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="my-4 overflow-hidden w-full flex justify-center [&>svg]:max-w-full [&>svg]:h-auto bg-white/30 rounded-xl p-4 border border-papaya-300/30 shadow-sm"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
