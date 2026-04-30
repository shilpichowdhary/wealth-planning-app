'use client'
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { TrustNode } from './nodes/TrustNode'
import { CompanyNode } from './nodes/CompanyNode'
import { IndividualNode } from './nodes/IndividualNode'
import { useCallback, useEffect, useRef, useState } from 'react'
import { layoutDiagram } from '@/lib/diagram-layout'
import { Shield, Building2, User, Plus, RotateCcw, Save, Check, type LucideIcon } from 'lucide-react'

const nodeTypes = {
  trust: TrustNode,
  company: CompanyNode,
  individual: IndividualNode,
}

// Edge styling tuned for the white canvas. Stroke is dim-grey (visible on
// white but not heavy); labels are dark pills with white text so they read
// like badges and remain legible whichever side of an edge they sit on.
const defaultEdgeOptions = {
  type: 'smoothstep' as const,
  animated: false,
  style: { stroke: '#6c6c6c', strokeOpacity: 0.55, strokeWidth: 1.5 },
  labelBgStyle: { fill: '#000000', fillOpacity: 0.85 },
  labelBgPadding: [6, 4] as [number, number],
  labelBgBorderRadius: 4,
  labelStyle: { fill: '#FFFFFF', fontSize: 11, fontWeight: 600 },
  markerEnd: { type: MarkerType.ArrowClosed, color: '#6c6c6c', width: 16, height: 16 },
}

interface Props {
  diagramData: { nodes: any[]; edges: any[] } | null
  title: string
  emptyLabel?: string
  onSave?: (nodes: Node[], edges: Edge[]) => Promise<void> | void
  savedAt?: string | null
}

export function StructureDiagram({ diagramData, title, emptyLabel, onSave, savedAt }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  // Monotonic counter for locally-added nodes — avoids collisions with
  // backend-generated ids like `node_0`.
  const localIdRef = useRef(1000)
  const nextLocalId = () => `local_${++localIdRef.current}`

  // Mark as dirty any time the rendered model diverges from what was loaded.
  // Uses a ref to hold the last-seen baseline so we don't falsely mark dirty
  // on the initial layout pass.
  const baselineRef = useRef<string>('')

  useEffect(() => {
    if (!diagramData || !diagramData.nodes?.length) {
      setNodes([])
      setEdges([])
      baselineRef.current = JSON.stringify({ nodes: [], edges: [] })
      setDirty(false)
      return
    }
    const laid = layoutDiagram(diagramData.nodes as Node[], diagramData.edges as Edge[])
    setNodes(laid.nodes)
    setEdges(laid.edges)
    baselineRef.current = JSON.stringify({ nodes: laid.nodes, edges: laid.edges })
    setDirty(false)
  }, [diagramData, setNodes, setEdges])

  // Compare current vs baseline whenever nodes or edges change to toggle dirty state.
  useEffect(() => {
    if (!baselineRef.current) return
    const current = JSON.stringify({ nodes, edges })
    setDirty(current !== baselineRef.current)
  }, [nodes, edges])

  const handleSave = useCallback(async () => {
    if (!onSave || saving) return
    setSaving(true)
    try {
      await onSave(nodes, edges)
      baselineRef.current = JSON.stringify({ nodes, edges })
      setDirty(false)
    } finally {
      setSaving(false)
    }
  }, [onSave, saving, nodes, edges])

  // Drag-to-connect: accept any connection and label it immediately.
  const onConnect = useCallback(
    (params: Connection) => {
      const label = typeof window !== 'undefined'
        ? window.prompt('Edge label (e.g. "settles", "owns 100%", "beneficial owner (60%)")', '') || ''
        : ''
      setEdges((eds) => addEdge({ ...params, label }, eds))
    },
    [setEdges],
  )

  // Double-click a node → edit label.
  const onNodeDoubleClick = useCallback(
    (_e: any, node: Node) => {
      const nextLabel = typeof window !== 'undefined'
        ? window.prompt('Entity label', String((node.data as any)?.label ?? ''))
        : null
      if (nextLabel === null) return
      setNodes((ns) =>
        ns.map((n) =>
          n.id === node.id ? { ...n, data: { ...n.data, label: nextLabel } } : n,
        ),
      )
    },
    [setNodes],
  )

  // Double-click an edge → edit label.
  const onEdgeDoubleClick = useCallback(
    (_e: any, edge: Edge) => {
      const nextLabel = typeof window !== 'undefined'
        ? window.prompt('Edge label', String(edge.label ?? ''))
        : null
      if (nextLabel === null) return
      setEdges((eds) => eds.map((e) => (e.id === edge.id ? { ...e, label: nextLabel } : e)))
    },
    [setEdges],
  )

  const addNode = (type: 'trust' | 'company' | 'individual') => {
    const defaults: Record<string, string> = {
      trust: 'New Trust',
      company: 'New PIC',
      individual: 'New Person',
    }
    const id = nextLocalId()
    setNodes((ns) => [
      ...ns,
      {
        id,
        type,
        position: { x: 40 + Math.random() * 80, y: 40 + Math.random() * 80 },
        data: { label: defaults[type], jurisdiction: '', role: '' },
        draggable: true,
      } as Node,
    ])
  }

  const relayout = () => {
    const laid = layoutDiagram(nodes, edges)
    setNodes(laid.nodes)
    setEdges(laid.edges)
  }

  const hasData = nodes.length > 0

  return (
    <div className="flex flex-col h-full bg-smoke">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-ink-200 bg-white/40">
        <div className="flex items-center gap-3 min-w-0">
          <h3 className="text-[11px] uppercase tracking-[0.16em] font-bold text-ink-800">{title}</h3>
          {hasData && (
            <span className="text-[11px] text-ink-500">
              {nodes.length} {nodes.length === 1 ? 'entity' : 'entities'} · {edges.length}{' '}
              {edges.length === 1 ? 'link' : 'links'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <ToolbarButton onClick={() => addNode('trust')} icon={Shield} label="Trust" />
          <ToolbarButton onClick={() => addNode('company')} icon={Building2} label="PIC" />
          <ToolbarButton onClick={() => addNode('individual')} icon={User} label="Person" />
          <span className="mx-1 h-4 w-px bg-ink-200" />
          <ToolbarButton onClick={relayout} icon={RotateCcw} label="Re-layout" />
          {onSave && hasData && (
            <>
              <span className="mx-1 h-4 w-px bg-ink-200" />
              <button
                onClick={handleSave}
                disabled={!dirty || saving}
                className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-bold transition ${
                  !dirty
                    ? 'border border-ink-300 bg-white text-ink-500 cursor-default'
                    : 'border border-lc-black bg-transparent text-lc-black hover:bg-lc-black hover:text-lc-white'
                }`}
                title={dirty ? 'Save diagram' : 'No changes to save'}
              >
                {saving ? (
                  <RotateCcw size={11} className="animate-spin" />
                ) : dirty ? (
                  <Save size={11} />
                ) : (
                  <Check size={11} />
                )}
                {saving ? 'Saving…' : dirty ? 'Save' : 'Saved'}
              </button>
            </>
          )}
        </div>
      </div>
      <div className="flex-1 relative" style={{ minHeight: 380 }}>
        {hasData ? (
          <>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeDoubleClick={onNodeDoubleClick}
              onEdgeDoubleClick={onEdgeDoubleClick}
              deleteKeyCode={['Backspace', 'Delete']}
              nodeTypes={nodeTypes}
              defaultEdgeOptions={defaultEdgeOptions}
              fitView
              fitViewOptions={{ padding: 0.25 }}
              proOptions={{ hideAttribution: true }}
              minZoom={0.3}
              maxZoom={1.5}
              nodesConnectable={true}
              nodesDraggable={true}
            >
              <Background color="rgba(0,0,0,0.07)" gap={24} size={1} />
              <Controls
                showInteractive={false}
                className="!bg-white !border-ink-300 !rounded-lg [&>button]:!bg-white [&>button]:!border-ink-300 [&>button]:!text-ink-600 [&>button:hover]:!bg-ink-100"
              />
            </ReactFlow>
            <div className="pointer-events-none absolute bottom-2 right-2 text-[10px] text-ink-400 bg-white/80 border border-ink-300 rounded px-2 py-1 backdrop-blur">
              Double-click to rename · drag handle to connect · Del to remove
            </div>
          </>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
            <p className="text-sm text-ink-500">{emptyLabel ?? 'No diagram yet.'}</p>
            <div className="flex gap-2">
              <ToolbarButton onClick={() => addNode('individual')} icon={User} label="Start with a Person" />
              <ToolbarButton onClick={() => addNode('trust')} icon={Shield} label="Start with a Trust" />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function ToolbarButton({
  onClick,
  icon: Icon,
  label,
}: {
  onClick: () => void
  icon: LucideIcon
  label: string
}) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1 rounded-md border border-ink-300 bg-white px-2 py-1 text-[11px] font-bold text-ink-800 hover:bg-ink-100 hover:text-lc-black hover:border-ink-400 transition"
    >
      <Plus size={11} className="text-ink-500" />
      <Icon size={11} />
      {label}
    </button>
  )
}
