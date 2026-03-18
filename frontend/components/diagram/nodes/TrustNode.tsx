import { Handle, Position } from '@xyflow/react'

export function TrustNode({ data }: { data: any }) {
  return (
    <div className="relative flex flex-col items-center" style={{ width: 160 }}>
      <Handle type="target" position={Position.Top} className="opacity-0" />
      {/* Triangle represents trust/foundation */}
      <svg width="120" height="100" viewBox="0 0 120 100">
        <polygon
          points="60,8 112,92 8,92"
          fill="#eff6ff"
          stroke="#1d4ed8"
          strokeWidth="2"
        />
        <foreignObject x="20" y="40" width="80" height="45">
          <div className="text-center text-xs font-semibold text-blue-900 leading-tight px-1">
            {data.label}
          </div>
        </foreignObject>
      </svg>
      {data.jurisdiction && (
        <span className="text-xs text-slate-500 mt-1">{data.jurisdiction}</span>
      )}
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  )
}
