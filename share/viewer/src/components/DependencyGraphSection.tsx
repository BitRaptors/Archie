import { useEffect, useRef, useState } from 'react'
import { Network, type Options } from 'vis-network'
import { DataSet } from 'vis-data'

interface DepNode {
  id: string
  label?: string
  component?: string
  files?: number
  in_cycle?: boolean
}

interface DepEdge {
  from: string
  to: string
  cross_component?: boolean
}

interface Props {
  graph: {
    nodes: DepNode[]
    edges: DepEdge[]
    cycles?: string[][]
  }
}

const COMPONENT_COLORS = [
  '#219ebc', '#ffb703', '#fb8500', '#8ecae6', '#023047',
  '#e63946', '#457b9d', '#2a9d8f', '#e9c46a', '#264653',
]

export function DependencyGraphSection({ graph }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const [selected, setSelected] = useState<DepNode | null>(null)

  useEffect(() => {
    if (!containerRef.current || !graph.nodes?.length) return

    const components = [...new Set(graph.nodes.map(n => n.component).filter(Boolean))]
    const colorMap: Record<string, string> = {}
    components.forEach((c, i) => {
      colorMap[c!] = COMPONENT_COLORS[i % COMPONENT_COLORS.length]
    })

    const nodes = new DataSet(
      graph.nodes.map(n => ({
        id: n.id,
        label: n.label || n.id.split('/').pop() || n.id,
        title: n.id,
        value: n.files || 1,
        color: {
          background: colorMap[n.component || ''] || '#8ecae6',
          border: n.in_cycle ? '#e63946' : colorMap[n.component || ''] || '#8ecae6',
          highlight: { background: '#ffb703', border: '#fb8500' },
        },
        borderWidth: n.in_cycle ? 3 : 1,
        font: { size: 11, color: '#023047' },
      }))
    )

    const edges = new DataSet(
      graph.edges.map((e, i) => ({
        id: `e${i}`,
        from: e.from,
        to: e.to,
        arrows: 'to',
        dashes: e.cross_component || false,
        color: { color: e.cross_component ? '#fb850080' : '#8ecae680' },
        width: 1,
      }))
    )

    const options: Options = {
      physics: {
        solver: 'barnesHut',
        barnesHut: { gravitationalConstant: -3000, springLength: 150 },
        stabilization: { iterations: 200 },
      },
      interaction: { hover: true, tooltipDelay: 100 },
      nodes: { shape: 'dot', scaling: { min: 8, max: 30 } },
      edges: { smooth: { enabled: true, type: 'continuous', roundness: 0.5 } },
    }

    const network = new Network(containerRef.current, { nodes, edges }, options)
    networkRef.current = network

    network.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0]
        const node = graph.nodes.find(n => n.id === nodeId) || null
        setSelected(node)
      } else {
        setSelected(null)
      }
    })

    network.once('stabilizationIterationsDone', () => {
      network.setOptions({ physics: { enabled: false } })
    })

    return () => {
      network.destroy()
      networkRef.current = null
    }
  }, [graph])

  const cycleCount = graph.cycles?.length || 0
  const incomingEdges = selected ? graph.edges.filter(e => e.to === selected.id) : []
  const outgoingEdges = selected ? graph.edges.filter(e => e.from === selected.id) : []

  return (
    <div className="flex gap-6">
      <div className="flex-1">
        <div className="flex gap-4 mb-4 text-xs text-ink/50">
          <span>{graph.nodes.length} modules</span>
          <span>{graph.edges.length} dependencies</span>
          {cycleCount > 0 && (
            <span className="text-brandy font-bold">{cycleCount} cycles</span>
          )}
        </div>
        <div
          ref={containerRef}
          className="w-full h-[500px] border border-papaya-400/60 rounded-2xl bg-white/60"
        />
        <div className="flex flex-wrap gap-3 mt-3 text-[10px] text-ink/40">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full border-2 border-red-500 bg-white inline-block" />
            In cycle
          </span>
          <span className="flex items-center gap-1">
            <span className="w-6 h-0 border-t-2 border-dashed border-brandy inline-block" />
            Cross-component
          </span>
        </div>
      </div>
      {selected && (
        <div className="w-64 shrink-0 bg-white/60 border border-papaya-400/60 rounded-2xl p-5 text-xs space-y-3">
          <p className="font-bold text-sm text-ink truncate" title={selected.id}>{selected.id}</p>
          {selected.component && (
            <p className="text-ink/40">Component: <span className="text-ink font-medium">{selected.component}</span></p>
          )}
          {selected.files != null && (
            <p className="text-ink/40">Files: <span className="text-ink font-medium">{selected.files}</span></p>
          )}
          <div>
            <p className="text-ink/40 mb-1">Incoming ({incomingEdges.length})</p>
            <div className="space-y-0.5 max-h-32 overflow-y-auto">
              {incomingEdges.map((e, i) => (
                <p key={i} className="text-ink/70 truncate">{e.from}</p>
              ))}
            </div>
          </div>
          <div>
            <p className="text-ink/40 mb-1">Outgoing ({outgoingEdges.length})</p>
            <div className="space-y-0.5 max-h-32 overflow-y-auto">
              {outgoingEdges.map((e, i) => (
                <p key={i} className="text-ink/70 truncate">{e.to}</p>
              ))}
            </div>
          </div>
          {selected.in_cycle && (
            <p className="text-brandy font-bold">Part of a dependency cycle</p>
          )}
        </div>
      )}
    </div>
  )
}
