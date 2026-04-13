import { useEffect, useRef, useState } from 'react'

interface MermaidDiagramProps {
  chart: string
}

// Global initialization state to avoid multiple re-initializations
let isInitialized = false;

export function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function render() {
      try {
        const mermaid = (await import('mermaid')).default

        if (!isInitialized) {
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
          } as never)
          isInitialized = true;
        }

        const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

        let cleanChart = chart.trim()
        if (!cleanChart) return

        // Quote node labels that contain characters mermaid chokes on (<br/>, =, +, /, (), :, comma).
        // Matches `Word[content]` and wraps content in quotes unless already quoted.
        // Leaves `[[x]]`, `[(x)]`, `[/x/]` (special shapes) alone by requiring a word-char prefix.
        cleanChart = cleanChart.replace(
          /(\b[\w.-]+)\[((?!")[^\]]*)\]/g,
          (m, id, label) => {
            // Skip if label already looks quoted or is empty
            if (!label || label.startsWith('"')) return m
            // Only quote if label contains a problematic char
            if (!/[<>/+=():,&]/.test(label)) return m
            // Escape any embedded quotes
            const safe = label.replace(/"/g, '#quot;')
            return `${id}["${safe}"]`
          }
        )

        // Function to perform render and catch internal Mermaid UI injection
        const doRender = async (cid: string, code: string) => {
          // Passing a dummy container helps Mermaid NOT to inject into body
          const tempDiv = document.createElement('div');
          tempDiv.style.display = 'none';
          document.body.appendChild(tempDiv);

          try {
            const result = await mermaid.render(cid, code, tempDiv);
            document.body.removeChild(tempDiv);
            return result.svg;
          } catch (err) {
            if (document.body.contains(tempDiv)) {
              document.body.removeChild(tempDiv);
            }
            throw err;
          }
        }

        try {
          const rendered = await doRender(id, cleanChart);
          if (!cancelled) {
            setSvg(rendered)
            setError(null)
          }
        } catch (renderErr: any) {
          // Retry with original chart if quoted one failed
          try {
            const rendered = await doRender(id + '-retry', chart.trim())
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
          console.warn('Mermaid render failure:', err.message);
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
      className="my-4 overflow-x-auto w-full flex justify-center [&>svg]:max-w-full [&>svg]:h-auto [&>svg]:min-h-[200px] bg-white/30 rounded-xl p-4 border border-papaya-300/30 shadow-sm"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
