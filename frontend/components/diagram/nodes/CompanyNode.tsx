import { Handle, Position } from '@xyflow/react'
import { Building2 } from 'lucide-react'

export function CompanyNode({ data }: { data: any }) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-md bg-lc-black border border-ink-600 px-4 py-3"
      style={{ minWidth: 200, minHeight: 80 }}
    >
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <div className="flex items-center gap-1.5 mb-1">
        <Building2 size={12} className="text-ink-300" />
        <div className="text-[11px] font-bold text-lc-white text-center leading-tight">
          {data.label}
        </div>
      </div>
      {data.jurisdiction && (
        <div className="text-[10px] uppercase tracking-[0.14em] text-lc-red font-bold">
          {data.jurisdiction}
        </div>
      )}
      {data.role && (
        <div className="text-[10px] text-ink-300 mt-0.5">{data.role}</div>
      )}
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  )
}
