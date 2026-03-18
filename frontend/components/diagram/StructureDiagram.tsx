'use client'
import { ReactFlow, Background, Controls, useNodesState, useEdgesState, type Node, type Edge } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { TrustNode } from './nodes/TrustNode'
import { CompanyNode } from './nodes/CompanyNode'
import { IndividualNode } from './nodes/IndividualNode'
import { useEffect } from 'react'

const nodeTypes = {
  trust: TrustNode,
  company: CompanyNode,
  individual: IndividualNode,
}

interface Props {
  diagramData: { nodes: any[]; edges: any[] } | null
  title: string
}

export function StructureDiagram({ diagramData, title }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    if (diagramData) {
      setNodes(diagramData.nodes)
      setEdges(diagramData.edges)
    }
  }, [diagramData])

  return (
    <div className="flex flex-col h-full">
      <h3 className="text-sm font-semibold text-slate-600 px-3 py-2 border-b">{title}</h3>
      <div className="flex-1" style={{ minHeight: 380 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#e2e8f0" gap={20} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  )
}
