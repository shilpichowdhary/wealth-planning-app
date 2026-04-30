import { Handle, Position } from '@xyflow/react'
import { Building2 } from 'lucide-react'

// Width is fixed (not just min-) so dagre's pre-layout NODE_SIZE estimate in
// lib/diagram-layout.ts matches the rendered box. Long labels (e.g. "Indian
// Assets (Real Estate + Equities) — Ring-Fenced") wrap onto multiple lines
// rather than expanding the box horizontally and overlapping siblings.
const NODE_W = 220

export function CompanyNode({ data }: { data: any }) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-md bg-smoke border border-ink-400 px-4 py-3"
      style={{ width: NODE_W, minHeight: 80 }}
    >
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <div className="flex items-start gap-1.5 mb-1 w-full">
        <Building2 size={12} className="text-ink-600 mt-0.5 shrink-0" />
        <div className="flex-1 text-[11px] font-bold text-lc-black text-center leading-tight break-words">
          {data.label}
        </div>
      </div>
      {data.jurisdiction && (
        <div className="text-[10px] uppercase tracking-[0.14em] text-lc-red font-bold text-center">
          {data.jurisdiction}
        </div>
      )}
      {data.role && (
        <div className="text-[10px] text-ink-600 mt-0.5 text-center">{data.role}</div>
      )}
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  )
}
