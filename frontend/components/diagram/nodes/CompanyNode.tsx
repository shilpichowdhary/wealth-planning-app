import { Handle, Position } from '@xyflow/react'

export function CompanyNode({ data }: { data: any }) {
  return (
    <div
      className="flex flex-col items-center justify-center bg-slate-50 border-2 border-slate-700 rounded-md px-4 py-3"
      style={{ minWidth: 160, minHeight: 64 }}
    >
      <Handle type="target" position={Position.Top} className="opacity-0" />
      <div className="text-xs font-semibold text-slate-800 text-center leading-tight">
        {data.label}
      </div>
      {data.jurisdiction && (
        <div className="text-xs text-slate-500 mt-1">{data.jurisdiction}</div>
      )}
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  )
}
