import dagre from '@dagrejs/dagre'
import type { Node, Edge } from '@xyflow/react'

// Approximate bounding-box sizes per node type — dagre needs these to route
// edges and avoid overlap. Must match the FIXED dimensions in
// components/diagram/nodes/*.tsx (CompanyNode width=220 with wrapping;
// IndividualNode width=120; TrustNode width≈160 around the triangle).
// Heights are upper-bounds because long wrapped labels add lines.
const NODE_SIZE: Record<string, { width: number; height: number }> = {
  trust: { width: 180, height: 150 },
  company: { width: 220, height: 110 },
  individual: { width: 130, height: 130 },
}

const DEFAULT_SIZE = { width: 220, height: 110 }

export interface LayoutOptions {
  /** 'auto' (default) tries TB and LR and picks whichever aspect ratio is
   *  closer to `canvasAspect`. Pass 'TB' or 'LR' to force one. */
  direction?: 'auto' | 'TB' | 'LR'
  rankSep?: number // gap between hierarchy levels
  nodeSep?: number // gap between siblings
  /** Width / height of the panel the diagram will live in. Used by 'auto'
   *  to pick the orientation. Default 2.0 — most users have wide viewports
   *  with the diagram filling the right pane minus a sidebar. */
  canvasAspect?: number
}

interface DagreResult {
  nodes: Node[]
  width: number
  height: number
  direction: 'TB' | 'LR'
}

function runDagre(
  direction: 'TB' | 'LR',
  rankSep: number,
  nodeSep: number,
  nodes: Node[],
  edges: Edge[],
): DagreResult {
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

  const laid: Node[] = nodes.map((n) => {
    const pos = g.node(n.id)
    const size = NODE_SIZE[n.type ?? ''] ?? DEFAULT_SIZE
    return {
      ...n,
      // dagre returns the node's center; React Flow wants top-left.
      position: { x: pos.x - size.width / 2, y: pos.y - size.height / 2 },
      draggable: true,
    }
  })
  const graph = g.graph()
  return {
    nodes: laid,
    width: graph.width ?? 0,
    height: graph.height ?? 1,
    direction,
  }
}

/**
 * Apply a hierarchical layout using dagre. By default ('auto') tries both
 * top-down (TB) and left-to-right (LR) and picks whichever aspect ratio is
 * closer to the panel's, so deep hierarchies don't get squashed vertically
 * when the panel is wide. Matches the same logic the PDF deck uses so the
 * editor view and the rendered chart stay visually consistent.
 *
 * Edges are returned as-is. Nodes whose type isn't in NODE_SIZE get DEFAULT_SIZE.
 */
export function layoutDiagram(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {},
): { nodes: Node[]; edges: Edge[] } {
  // Defaults tuned for legibility when multiple edges fan into the same node
  // (e.g. settlor / trustee / protector all pointing at the trust). Wider
  // node separation spreads sibling sources horizontally, and taller rank
  // separation gives midpoint edge labels vertical breathing room.
  const { direction = 'auto', rankSep = 140, nodeSep = 110, canvasAspect = 2.0 } = options

  if (nodes.length === 0) return { nodes, edges }

  if (direction === 'TB' || direction === 'LR') {
    return { nodes: runDagre(direction, rankSep, nodeSep, nodes, edges).nodes, edges }
  }

  // 'auto' — compute both and pick the orientation whose aspect ratio is
  // closer to the panel's. For LR we swap rank/node sep so the rank axis
  // (now horizontal) keeps tighter spacing and siblings (now vertical)
  // get the breathing room.
  const tb = runDagre('TB', rankSep, nodeSep, nodes, edges)
  const lr = runDagre('LR', 200, 80, nodes, edges)
  const score = (g: DagreResult) => Math.abs(Math.log(g.width / Math.max(g.height, 1) / canvasAspect))
  const best = score(lr) < score(tb) ? lr : tb
  return { nodes: best.nodes, edges }
}
