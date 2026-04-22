import { Handle, Position } from '@xyflow/react'
import { User } from 'lucide-react'

export function IndividualNode({ data }: { data: any }) {
  return (
    <div className="flex flex-col items-center gap-1" style={{ width: 120 }}>
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <div className="h-14 w-14 rounded-full bg-lc-black border-2 border-lc-red flex items-center justify-center">
        <User size={22} className="text-lc-red" />
      </div>
      <div className="text-[11px] font-bold text-lc-white text-center leading-tight max-w-[110px] mt-1">
        {data.label}
      </div>
      {data.role && (
        <div className="text-[10px] uppercase tracking-[0.14em] text-ink-300 font-bold">
          {data.role}
        </div>
      )}
      {data.jurisdiction && (
        <div className="text-[10px] text-lc-red font-bold">{data.jurisdiction}</div>
      )}
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  )
}
