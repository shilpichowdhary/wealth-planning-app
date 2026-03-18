import { Handle, Position } from '@xyflow/react'
import { User } from 'lucide-react'

export function IndividualNode({ data }: { data: any }) {
  return (
    <div className="flex flex-col items-center gap-1" style={{ width: 100 }}>
      <Handle type="target" position={Position.Top} className="opacity-0" />
      <div className="w-12 h-12 rounded-full bg-amber-100 border-2 border-amber-400 flex items-center justify-center">
        <User size={24} className="text-amber-700" />
      </div>
      <div className="text-xs font-semibold text-slate-700 text-center leading-tight max-w-[90px]">
        {data.label}
      </div>
      {data.role && (
        <div className="text-xs text-slate-500">{data.role}</div>
      )}
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  )
}
