import dagre from '@dagrejs/dagre'
import type { Node, Edge } from '@xyflow/react'

// Approximate bounding-box sizes per node type — dagre needs these to route edges.
// Match the actual rendered widths/heights in components/diagram/nodes/*.tsx.
const NODE_SIZE: Record<string, { width: number; height: number }> = {
  trust: { width: 180, height: 140 },
  company: { width: 200, height: 96 },
  individual: { width: 120, height: 120 },
}

const DEFAULT_SIZE = { width: 200, height: 96 }

export interface LayoutOptions {
  direction?: 'TB' | 'LR'
  rankSep?: number // gap between hierarchy levels
  nodeSep?: number // gap between siblings
}

/**
 * Apply a top-down hierarchical layout using dagre. Returns a new array of
 * nodes with `position` computed from the edge graph. Edges are returned
 * as-is. Nodes whose type isn't in NODE_SIZE get DEFAULT_SIZE.
 */
export function layoutDiagram(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {},
): { nodes: Node[]; edges: Edge[] } {
  const { direction = 'TB', rankSep = 80, nodeSep = 60 } = options

  if (nodes.length === 0) return { nodes, edges }

  const g = new dagre.graphlib.Graph()
  g.setGraph({
    rankdir: direction,
    ranksep: rankSep,
    nodesep: nodeSep,
    marginx: 30,
    marginy: 30,
  })
  g.setDefaultEdgeLabel(() => ({}))

  for (const n of nodes) {
    const size = NODE_SIZE[n.type ?? ''] ?? DEFAULT_SIZE
    g.setNode(n.id, { width: size.width, height: size.height })
  }
  for (const e of edges) {
    g.setEdge(e.source, e.target)
  }

  dagre.layout(g)

  const laidOut: Node[] = nodes.map((n) => {
    const pos = g.node(n.id)
    const size = NODE_SIZE[n.type ?? ''] ?? DEFAULT_SIZE
    return {
      ...n,
      // dagre returns the node's center; React Flow wants top-left.
      position: { x: pos.x - size.width / 2, y: pos.y - size.height / 2 },
      // Reset any per-node flags that'd lock position on re-layout.
      draggable: true,
    }
  })

  return { nodes: laidOut, edges }
}
