import { useEffect, useRef, useState } from 'react'
import { Minus, Plus, RotateCcw } from 'lucide-react'
import { getNextDiagramZoom, type DiagramZoomAction } from '@/lib/diagramZoom'

interface MermaidDiagramProps {
  chart: string
}

// Global initialization state to avoid multiple re-initializations
let isInitialized = false;

export function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)

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
              primaryColor: '#CEEEF6',      // teal-50
              primaryTextColor: '#023047',  // ink
              primaryBorderColor: '#219EBC', // teal
              lineColor: '#219EBC',         // teal
              secondaryColor: '#FFB703',    // tangerine
              tertiaryColor: '#FB8500',     // brandy
              fontFamily: 'Outfit, Inter, ui-sans-serif, system-ui, sans-serif',
              fontSize: '14px',
              mainBkg: '#FFFFFF',
              nodeBorder: '#219EBC',
              clusterBkg: '#E8F4FA',        // papaya-50
              clusterBorder: '#8ECAE6',     // papaya
              titleColor: '#023047',
              edgeLabelBackground: '#FFFFFF',
            },
            securityLevel: 'loose',
            suppressErrorUI: true,
          } as never)
          isInitialized = true;
        }

        const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

        const original = chart.trim()
        if (!original) return

        // Aggressive quoting: wraps `Word[label]` content in quotes if it has
        // mermaid-unfriendly chars. Used only as a fallback if the original fails.
        const quoted = original.replace(
          /(\b[\w.-]+)\[((?!")[^\]]*)\]/g,
          (m, id, label) => {
            if (!label || label.startsWith('"')) return m
            if (!/[<>/+=():,&]/.test(label)) return m
            return `${id}["${label.replace(/"/g, '#quot;')}"]`
          }
        )
        let cleanChart = original

        // Function to perform render and catch internal Mermaid UI injection
        const doRender = async (cid: string, code: string) => {
          // Passing a dummy container helps Mermaid NOT to inject into body
          // Must be visible (not display:none) so mermaid can measure text widths.
          // Position off-screen instead.
          const tempDiv = document.createElement('div');
          tempDiv.style.position = 'absolute';
          tempDiv.style.left = '-99999px';
          tempDiv.style.top = '0';
          tempDiv.style.visibility = 'hidden';
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
          // Original failed — try with aggressive label quoting
          try {
            const rendered = await doRender(id + '-retry', quoted)
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

  const updateZoom = (action: DiagramZoomAction) => {
    setZoom((current) => getNextDiagramZoom(current, action))
  }

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (!event.ctrlKey && !event.metaKey) return

    event.preventDefault()
    updateZoom(event.deltaY < 0 ? 'in' : 'out')
  }

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
    <div className="my-4 overflow-hidden bg-white/30 rounded-xl border border-papaya-300/30 shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-papaya-300/30 px-3 py-2">
        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/35">
          Zoom {Math.round(zoom * 100)}%
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => updateZoom('out')}
            className="h-8 w-8 rounded-md border border-papaya-300 bg-white/70 text-ink/60 hover:text-ink hover:bg-white transition-colors flex items-center justify-center"
            aria-label="Zoom out"
          >
            <Minus className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => updateZoom('reset')}
            className="h-8 px-2 rounded-md border border-papaya-300 bg-white/70 text-[10px] font-black uppercase tracking-widest text-ink/50 hover:text-ink hover:bg-white transition-colors inline-flex items-center gap-1"
            aria-label="Reset zoom"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
          <button
            type="button"
            onClick={() => updateZoom('in')}
            className="h-8 w-8 rounded-md border border-papaya-300 bg-white/70 text-ink/60 hover:text-ink hover:bg-white transition-colors flex items-center justify-center"
            aria-label="Zoom in"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        onWheel={handleWheel}
        className="w-full max-h-[70vh] overflow-auto p-4 overscroll-contain"
      >
        <div
          className="mx-auto [&_svg]:!w-full [&_svg]:!max-w-none [&_svg]:!h-auto [&_svg]:min-h-[200px]"
          style={{ width: `${zoom * 100}%`, minWidth: `${zoom * 100}%` }}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
    </div>
  )
}
