'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { ArrowLeft, ArrowRight, Check } from 'lucide-react'

const ASSET_CLASSES = [
  'equities',
  'fixed_income',
  'real_estate',
  'private_equity',
  'hedge_funds',
  'cash',
  'crypto',
  'commodities',
]

// Jurisdictions where client assets can be held. Broader than the KB's
// research jurisdictions — includes offshore financial centres.
const ASSET_JURISDICTIONS = [
  'US',
  'UK',
  'Singapore',
  'UAE',
  'India',
  'Taiwan',
  'China',
  'Hong Kong',
  'Cayman Islands',
  'BVI',
  'Jersey',
  'Guernsey',
  'Switzerland',
  'Luxembourg',
  'Ireland',
]

const OBJECTIVES = [
  'tax_optimisation',
  'succession_planning',
  'asset_protection',
  'philanthropy',
  'liquidity_management',
  'regulatory_compliance',
  'privacy',
  'consolidation',
]

const STEPS = ['Client', 'Assets', 'Structures', 'Objectives'] as const

export default function NewCasePage() {
  const { data: session } = useSession()
  const router = useRouter()
  const token = session?.accessToken ?? ''

  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const [clientName, setClientName] = useState('')
  const [nationality, setNationality] = useState('')
  const [domicile, setDomicile] = useState('')
  const [taxResidency, setTaxResidency] = useState('')
  const [assetClasses, setAssetClasses] = useState<string[]>([])
  const [assetJurisdictions, setAssetJurisdictions] = useState<string[]>([])
  const [existingStructures, setExistingStructures] = useState('')
  const [objectives, setObjectives] = useState<string[]>([])

  async function handleSubmit() {
    if (!token) {
      setError('Not authenticated')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

      const caseRes = await fetch(`${apiUrl}/cases/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ client_name: clientName }),
      })
      if (!caseRes.ok) throw new Error(`Failed to create case: ${await caseRes.text()}`)
      const caseData = await caseRes.json()
      const caseId = caseData.case_id

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

  const inputCls =
    'w-full bg-ink-850 border border-ink-700 rounded-lg px-4 py-2.5 text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none focus:border-brass-500 focus:ring-2 focus:ring-brass-500/20 transition'

  return (
    <div className="max-w-2xl mx-auto w-full px-8 py-10">
      <header className="mb-8 animate-fade-in-up">
        <p className="text-[11px] uppercase tracking-[0.2em] text-ink-400 font-medium">
          Step {step + 1} of {STEPS.length} — {STEPS[step]}
        </p>
        <h1 className="mt-2 font-display text-[38px] leading-[1.05] tracking-tight text-ink-100">
          New case<em className="italic text-brass-400 font-normal">.</em>
        </h1>

        {/* Step indicator */}
        <div className="flex gap-1.5 mt-5">
          {STEPS.map((label, i) => (
            <div key={label} className="flex-1 space-y-1.5">
              <div
                className={`h-1 rounded-full transition-all ${
                  i < step
                    ? 'bg-brass-500'
                    : i === step
                    ? 'bg-lc-red'
                    : 'bg-ink-800'
                }`}
              />
              <p
                className={`text-[10px] uppercase tracking-[0.14em] font-medium ${
                  i === step ? 'text-ink-100' : 'text-ink-500'
                }`}
              >
                {label}
              </p>
            </div>
          ))}
        </div>
      </header>

      <div className="rounded-2xl border border-ink-800 bg-ink-900 p-6 space-y-5 animate-fade-in-up" style={{ animationDelay: '0.05s' }}>
        {step === 0 && (
          <>
            <Field label="Client name" required>
              <input
                type="text"
                value={clientName}
                onChange={e => setClientName(e.target.value)}
                placeholder="Full name"
                className={inputCls}
                required
              />
            </Field>
            <Field label="Nationality">
              <input
                type="text"
                value={nationality}
                onChange={e => setNationality(e.target.value)}
                placeholder="e.g. British"
                className={inputCls}
              />
            </Field>
            <Field label="Domicile">
              <input
                type="text"
                value={domicile}
                onChange={e => setDomicile(e.target.value)}
                placeholder="e.g. UK"
                className={inputCls}
              />
            </Field>
            <Field label="Tax residency">
              <input
                type="text"
                value={taxResidency}
                onChange={e => setTaxResidency(e.target.value)}
                placeholder="e.g. Singapore"
                className={inputCls}
              />
            </Field>
          </>
        )}

        {step === 1 && (
          <>
            <ChipGroup
              label="Asset classes"
              options={ASSET_CLASSES}
              selected={assetClasses}
              onChange={setAssetClasses}
            />
            <ChipGroup
              label="Asset jurisdictions"
              options={ASSET_JURISDICTIONS}
              selected={assetJurisdictions}
              onChange={setAssetJurisdictions}
            />
          </>
        )}

        {step === 2 && (
          <Field label="Describe any existing structures">
            <textarea
              value={existingStructures}
              onChange={e => setExistingStructures(e.target.value)}
              placeholder="e.g. BVI holding company, UK family trust, Singapore family office…"
              rows={6}
              className={`${inputCls} resize-none`}
            />
          </Field>
        )}

        {step === 3 && (
          <ChipGroup
            label="Select planning objectives"
            options={OBJECTIVES}
            selected={objectives}
            onChange={setObjectives}
          />
        )}

        {error && (
          <div className="rounded-lg border border-ember-500/40 bg-ember-500/10 px-3 py-2 text-sm text-ember-500">
            {error}
          </div>
        )}

        <div className="flex items-center justify-between pt-3">
          <button
            onClick={() => setStep(s => s - 1)}
            disabled={step === 0}
            className="inline-flex items-center gap-2 px-3 py-2 text-sm text-ink-300 border border-ink-700 rounded-lg hover:bg-ink-800 hover:text-ink-100 transition disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ArrowLeft size={14} />
            Back
          </button>
          {step < STEPS.length - 1 ? (
            <button
              onClick={() => {
                if (step === 0 && !clientName.trim()) {
                  setError('Client name is required')
                  return
                }
                setError('')
                setStep(s => s + 1)
              }}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-sm bg-lc-red text-lc-white rounded-lg hover:bg-lc-red/90 transition font-semibold"
            >
              Next
              <ArrowRight size={14} />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-sm bg-lc-red text-lc-white rounded-lg hover:bg-lc-red/90 transition font-semibold disabled:opacity-50"
            >
              <Check size={14} />
              {submitting ? 'Creating…' : 'Create case'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({
  label,
  required,
  children,
}: {
  label: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-[0.16em] text-ink-400 font-medium mb-1.5">
        {label}
        {required && <span className="text-brass-400 ml-1">*</span>}
      </label>
      {children}
    </div>
  )
}

function ChipGroup({
  label,
  options,
  selected,
  onChange,
}: {
  label: string
  options: string[]
  selected: string[]
  onChange: (v: string[]) => void
}) {
  const toggle = (opt: string) =>
    selected.includes(opt) ? onChange(selected.filter(x => x !== opt)) : onChange([...selected, opt])

  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.16em] text-ink-400 font-medium mb-2">{label}</p>
      <div className="flex flex-wrap gap-2">
        {options.map(opt => {
          const active = selected.includes(opt)
          return (
            <button
              key={opt}
              type="button"
              onClick={() => toggle(opt)}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] transition ${
                active
                  ? 'border-brass-500/60 bg-brass-500/10 text-brass-300'
                  : 'border-ink-700 bg-ink-850 text-ink-300 hover:border-ink-600 hover:text-ink-100'
              }`}
            >
              {active && <Check size={12} />}
              {opt.replace(/_/g, ' ')}
            </button>
          )
        })}
      </div>
    </div>
  )
}
