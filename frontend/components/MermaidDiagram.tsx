'use client'

import { useEffect, useRef, useState } from 'react'

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
            primaryColor: '#CEEEF6', // papaya-50/100
            primaryTextColor: '#023047', // ink
            primaryBorderColor: '#219EBC', // teal
            lineColor: '#219EBC',
            secondaryColor: '#FFB703', // tangerine
            tertiaryColor: '#FB8500', // brandy
            fontFamily: 'ui-sans-serif, system-ui, sans-serif',
            fontSize: '14px',
          },
          securityLevel: 'loose',
        })

        const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
        // Ensure chart is trimmed and handled correctly
        const cleanChart = chart.trim()
        if (!cleanChart) return

        const { svg: rendered } = await mermaid.render(id, cleanChart)
        if (!cancelled) {
          setSvg(rendered)
          setError(null)
        }
      } catch (err: any) {
        if (!cancelled) {
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
        <pre className="text-xs text-amber-900 font-mono whitespace-pre-wrap overflow-x-auto">{chart}</pre>
      </div>
    )
  }

  if (!svg) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
        Rendering diagram...
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="my-4 overflow-hidden w-full flex justify-center [&>svg]:max-w-full [&>svg]:h-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
