'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'

const ASSET_CLASSES = ['equities', 'fixed_income', 'real_estate', 'private_equity', 'hedge_funds', 'cash', 'crypto', 'commodities']
const JURISDICTIONS = ['US', 'UK', 'Singapore', 'Cayman Islands', 'BVI', 'Jersey', 'Guernsey', 'Switzerland', 'UAE', 'Hong Kong', 'Luxembourg', 'Ireland']
const OBJECTIVES = ['tax_optimisation', 'succession_planning', 'asset_protection', 'philanthropy', 'liquidity_management', 'regulatory_compliance', 'privacy', 'consolidation']

function CheckboxGroup({ label, options, selected, onChange }: {
  label: string
  options: string[]
  selected: string[]
  onChange: (val: string[]) => void
}) {
  const toggle = (opt: string) => {
    if (selected.includes(opt)) onChange(selected.filter(x => x !== opt))
    else onChange([...selected, opt])
  }
  return (
    <div>
      <p className="text-sm font-medium text-slate-700 mb-2">{label}</p>
      <div className="flex flex-wrap gap-2">
        {options.map(opt => (
          <label key={opt} className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={selected.includes(opt)} onChange={() => toggle(opt)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
            <span className="text-sm text-slate-700">{opt.replace(/_/g, ' ')}</span>
          </label>
        ))}
      </div>
    </div>
  )
}

export default function NewCasePage() {
  const { data: session } = useSession()
  const router = useRouter()
  const token = (session as any)?.accessToken as string

  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  // Step 0 fields
  const [clientName, setClientName] = useState('')
  const [nationality, setNationality] = useState('')
  const [domicile, setDomicile] = useState('')
  const [taxResidency, setTaxResidency] = useState('')

  // Step 1 fields
  const [assetClasses, setAssetClasses] = useState<string[]>([])
  const [assetJurisdictions, setAssetJurisdictions] = useState<string[]>([])

  // Step 2 fields
  const [existingStructures, setExistingStructures] = useState('')

  // Step 3 fields
  const [objectives, setObjectives] = useState<string[]>([])

  async function handleSubmit() {
    if (!token) { setError('Not authenticated'); return }
    setSubmitting(true)
    setError('')
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

      // Create case
      const caseRes = await fetch(`${apiUrl}/cases/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ client_name: clientName }),
      })
      if (!caseRes.ok) throw new Error(`Failed to create case: ${await caseRes.text()}`)
      const caseData = await caseRes.json()
      const caseId = caseData.case_id

      // Save profile
      const profileRes = await fetch(`${apiUrl}/cases/${caseId}/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          nationality,
          domicile,
          tax_residency: taxResidency,
          asset_classes: assetClasses,
          asset_jurisdictions: assetJurisdictions,
          existing_structures: existingStructures,
          objectives,
        }),
      })
      if (!profileRes.ok) throw new Error(`Failed to save profile: ${await profileRes.text()}`)

      router.push(`/cases/${caseId}`)
    } catch (err: any) {
      setError(err.message || 'An error occurred')
      setSubmitting(false)
    }
  }

  const inputCls = 'w-full border border-slate-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">New Case</h1>
        <p className="text-slate-500 text-sm mt-1">Step {step + 1} of 4</p>
        <div className="flex gap-1 mt-3">
          {[0, 1, 2, 3].map(i => (
            <div key={i} className={`h-1.5 flex-1 rounded-full ${i <= step ? 'bg-blue-600' : 'bg-slate-200'}`} />
          ))}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
        {step === 0 && (
          <>
            <h2 className="text-lg font-semibold text-slate-900">Client Information</h2>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Client Name *</label>
              <input type="text" value={clientName} onChange={e => setClientName(e.target.value)}
                placeholder="Full name" className={inputCls} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Nationality</label>
              <input type="text" value={nationality} onChange={e => setNationality(e.target.value)}
                placeholder="e.g. British" className={inputCls} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Domicile</label>
              <input type="text" value={domicile} onChange={e => setDomicile(e.target.value)}
                placeholder="e.g. UK" className={inputCls} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Tax Residency</label>
              <input type="text" value={taxResidency} onChange={e => setTaxResidency(e.target.value)}
                placeholder="e.g. Singapore" className={inputCls} />
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <h2 className="text-lg font-semibold text-slate-900">Assets</h2>
            <CheckboxGroup label="Asset Classes" options={ASSET_CLASSES} selected={assetClasses} onChange={setAssetClasses} />
            <CheckboxGroup label="Asset Jurisdictions" options={JURISDICTIONS} selected={assetJurisdictions} onChange={setAssetJurisdictions} />
          </>
        )}

        {step === 2 && (
          <>
            <h2 className="text-lg font-semibold text-slate-900">Existing Structures</h2>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Describe any existing structures</label>
              <textarea
                value={existingStructures}
                onChange={e => setExistingStructures(e.target.value)}
                placeholder="e.g. BVI holding company, UK family trust, Singapore family office..."
                rows={6}
                className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <h2 className="text-lg font-semibold text-slate-900">Objectives</h2>
            <CheckboxGroup label="Select planning objectives" options={OBJECTIVES} selected={objectives} onChange={setObjectives} />
          </>
        )}

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <div className="flex justify-between pt-2">
          <button
            onClick={() => setStep(s => s - 1)}
            disabled={step === 0}
            className="px-4 py-2 text-sm text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50 transition disabled:opacity-30"
          >
            Back
          </button>
          {step < 3 ? (
            <button
              onClick={() => {
                if (step === 0 && !clientName.trim()) { setError('Client name is required'); return }
                setError('')
                setStep(s => s + 1)
              }}
              className="px-6 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="px-6 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Create Case'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
