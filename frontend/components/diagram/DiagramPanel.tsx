'use client'
import { StructureDiagram } from './StructureDiagram'

interface Props {
  existingDiagram: { nodes: any[]; edges: any[] } | null
  recommendedDiagram: { nodes: any[]; edges: any[] } | null
}

export function DiagramPanel({ existingDiagram, recommendedDiagram }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 h-full border rounded-lg overflow-hidden bg-white shadow-sm">
      <div className="border-r">
        <StructureDiagram diagramData={existingDiagram} title="Existing Structure" />
      </div>
      <div>
        <StructureDiagram diagramData={recommendedDiagram} title="Recommended Structure" />
      </div>
    </div>
  )
}
