import { useMemo } from 'react'
import type { GraphPayload } from '../lib/types'

function colorFor(r: number) {
  if (r >= 0.7) return '#34d399'
  if (r >= 0.4) return '#fbbf24'
  return '#f87171'
}

export default function TopicGraph({ data }: { data: GraphPayload }) {
  const layout = useMemo(() => {
    const width = 960
    const height = 540
    const layers = data.layers.length ? data.layers : [data.nodes.map((n) => n.name)]
    const pos = new Map<string, { x: number; y: number }>()
    layers.forEach((layer, li) => {
      const x = ((li + 0.5) / Math.max(1, layers.length)) * (width - 80) + 40
      layer.forEach((name, ni) => {
        const y = ((ni + 0.5) / Math.max(1, layer.length)) * (height - 80) + 40
        pos.set(name, { x, y })
      })
    })
    // Place any missing nodes
    data.nodes.forEach((n, i) => {
      if (!pos.has(n.name)) {
        pos.set(n.name, { x: 80 + (i % 8) * 110, y: 80 + Math.floor(i / 8) * 70 })
      }
    })
    return { width, height, pos }
  }, [data])

  const byName = useMemo(() => Object.fromEntries(data.nodes.map((n) => [n.name, n])), [data])

  return (
    <div className="graph-wrap">
      <svg className="graph-svg" viewBox={`0 0 ${layout.width} ${layout.height}`}>
        {data.edges.map((e, i) => {
          const a = layout.pos.get(e.from)
          const b = layout.pos.get(e.to)
          if (!a || !b) return null
          return (
            <line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="rgba(148,163,184,0.28)"
              strokeWidth={1.5}
            />
          )
        })}
        {data.nodes.map((n) => {
          const p = layout.pos.get(n.name)
          if (!p) return null
          const node = byName[n.name]
          const fill = colorFor(node?.retrievability ?? 0.5)
          return (
            <g key={n.id} transform={`translate(${p.x}, ${p.y})`}>
              <circle r={16} fill={fill} opacity={0.2} />
              <circle r={8} fill={fill} stroke="#0a0e14" strokeWidth={2} />
              <text y={28} textAnchor="middle" fill="#e8eef7" fontSize={11}>
                {n.name}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
