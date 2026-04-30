'use client'
import { StructureDiagram } from './StructureDiagram'
import type { Node, Edge } from '@xyflow/react'

interface Props {
  existingDiagram: { nodes: any[]; edges: any[] } | null
  recommendedDiagram: { nodes: any[]; edges: any[] } | null
  onSave?: (nodes: Node[], edges: Edge[]) => Promise<void> | void
  savedAt?: string | null
}

export function DiagramPanel({ existingDiagram, recommendedDiagram, onSave, savedAt }: Props) {
  const hasExisting = !!existingDiagram?.nodes?.length
  const hasRecommended = !!recommendedDiagram?.nodes?.length

  if (hasExisting && hasRecommended) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 h-full gap-px bg-ink-100">
        <StructureDiagram
          diagramData={existingDiagram}
          title="Existing structure"
          onSave={onSave}
          savedAt={savedAt}
        />
        <StructureDiagram
          diagramData={recommendedDiagram}
          title="Recommended structure"
          onSave={onSave}
          savedAt={savedAt}
        />
      </div>
    )
  }

  const single = hasRecommended ? recommendedDiagram : existingDiagram
  const title = hasRecommended ? 'Recommended structure' : 'Existing structure'
  const emptyLabel = hasRecommended
    ? undefined
    : 'Ask the advisor to propose a structure — the flow diagram will render here.'

  return (
    <div className="h-full">
      <StructureDiagram
        diagramData={single}
        title={title}
        emptyLabel={emptyLabel}
        onSave={onSave}
        savedAt={savedAt}
      />
    </div>
  )
}
