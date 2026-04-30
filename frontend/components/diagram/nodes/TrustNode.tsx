import { Handle, Position } from '@xyflow/react'
import { Shield } from 'lucide-react'

export function TrustNode({ data }: { data: any }) {
  return (
    <div className="relative flex flex-col items-center" style={{ width: 180 }}>
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <div className="relative flex items-center justify-center" style={{ width: 160, height: 100 }}>
        {/* Solid triangle — Agile Red outline on Smart Black, no gradient per brand */}
        <svg width="160" height="100" viewBox="0 0 160 100" className="absolute inset-0">
          <polygon
            points="80,8 150,92 10,92"
            fill="#000000"
            stroke="#E50025"
            strokeWidth="2"
          />
        </svg>
        <div className="relative flex flex-col items-center gap-1 pt-5">
          <Shield size={14} className="text-lc-red" />
          <div className="text-center text-[11px] font-bold text-lc-white leading-tight px-2 max-w-[130px]">
            {data.label}
          </div>
        </div>
      </div>
      {data.jurisdiction && (
        <span className="mt-1 text-[10px] uppercase tracking-[0.14em] text-lc-red font-bold">
          {data.jurisdiction}
        </span>
      )}
      {data.role && (
        <span className="text-[10px] text-ink-600 mt-0.5">{data.role}</span>
      )}
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  )
}
