'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { signIn } from 'next-auth/react'
import { Lock, AlertTriangle, Check } from 'lucide-react'
import { LCLogoMark } from '@/components/brand/LCLogo'

interface InvitePreview {
  name: string
  email: string
  role: string
  expires_at: string
}

export default function InviteAcceptPage({ params }: { params: { token: string } }) {
  const router = useRouter()
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  const [preview, setPreview] = useState<InvitePreview | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${apiUrl}/auth/invite/${encodeURIComponent(params.token)}`)
      .then(async (r) => {
        const body = await r.json().catch(() => ({} as any))
        if (!r.ok) {
          // 410 means expired/used/revoked — pick the backend's own wording
          throw new Error(body?.detail || `Invite not valid (${r.status})`)
        }
        return body as InvitePreview
      })
      .then(setPreview)
      .catch((e) => setLoadError(e.message ?? 'Failed to load invite'))
      .finally(() => setLoading(false))
  }, [apiUrl, params.token])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitError(null)
    if (password.length < 12) {
      setSubmitError('Password must be at least 12 characters.')
      return
    }
    if (password !== confirm) {
      setSubmitError('Passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      const res = await fetch(
        `${apiUrl}/auth/invite/${encodeURIComponent(params.token)}/accept`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password }),
        },
      )
      const body = await res.json().catch(() => ({} as any))
      if (!res.ok) throw new Error(body?.detail || `Failed (${res.status})`)

      // Auto-sign-in via NextAuth credentials so the advisor lands on the
      // dashboard without having to re-type the password.
      const signin = await signIn('credentials', {
        email: preview?.email ?? body?.user?.email,
        password,
        redirect: false,
      })
      if (signin?.error) {
        // Fall back to a clean login screen if auto-sign-in fails.
        router.push('/login?accepted=1')
        return
      }
      router.push('/dashboard')
    } catch (err: any) {
      setSubmitError(err?.message ?? 'Could not accept invite')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-lc-black flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-[440px]">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <LCLogoMark size={36} />
          <span className="font-sans text-[12px] uppercase tracking-[0.16em] text-lc-white font-bold">
            Lighthouse <span className="text-lc-red">·</span> Canton
          </span>
        </div>

        <div className="rounded-2xl border border-ink-800 bg-ink-900 p-8 animate-fade-in-up">
          {loading ? (
            <p className="text-sm text-ink-400">Checking invite…</p>
          ) : loadError ? (
            <InviteBroken message={loadError} />
          ) : preview ? (
            <>
              <p className="text-[11px] uppercase tracking-[0.18em] text-lc-red font-bold">
                Invite ready
              </p>
              <h1 className="mt-2 font-display text-[28px] leading-tight text-lc-white">
                Welcome, {preview.name.split(' ')[0]}.
              </h1>
              <p className="mt-2 text-sm text-ink-300">
                Set a password for <span className="text-lc-white">{preview.email}</span> to activate
                your Wealth Planning console access.
              </p>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <PasswordField
                  label="New password"
                  value={password}
                  onChange={setPassword}
                  autoFocus
                />
                <PasswordField label="Confirm password" value={confirm} onChange={setConfirm} />
                <PasswordChecklist pw={password} confirm={confirm} />

                {submitError && (
                  <div className="rounded-lg border border-lc-red bg-lc-red/10 px-3 py-2 text-sm text-lc-red flex items-center gap-2">
                    <AlertTriangle size={14} />
                    {submitError}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-lc-red text-lc-white py-3 text-sm font-bold hover:bg-lc-red/90 transition disabled:opacity-50"
                >
                  <Lock size={14} />
                  {submitting ? 'Activating…' : 'Set password & sign in'}
                </button>

                <p className="text-[11px] text-ink-400 leading-relaxed">
                  Invite expires {new Date(preview.expires_at).toLocaleString()}. Internal use only.
                </p>
              </form>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function InviteBroken({ message }: { message: string }) {
  return (
    <>
      <div className="flex items-center gap-2 text-lc-red mb-3">
        <AlertTriangle size={16} />
        <span className="text-[11px] uppercase tracking-[0.18em] font-bold">Invite cannot be used</span>
      </div>
      <h1 className="font-display text-[26px] leading-tight text-lc-white">Link not valid.</h1>
      <p className="mt-2 text-sm text-ink-300">{message}</p>
      <p className="mt-4 text-sm text-ink-300">
        Ask your administrator to issue a fresh invite — they can resend it from the Advisors page.
      </p>
    </>
  )
}

function PasswordField({
  label,
  value,
  onChange,
  autoFocus,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  autoFocus?: boolean
}) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-[0.16em] text-ink-300 font-bold mb-1.5">
        {label}
      </label>
      <input
        type="password"
        autoFocus={autoFocus}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="••••••••••••"
        minLength={12}
        maxLength={72}
        required
        className="w-full bg-ink-850 border border-ink-700 rounded-lg px-4 py-3 text-[15px] text-lc-white placeholder:text-ink-500 focus:outline-none focus:border-lc-red focus:ring-2 focus:ring-lc-red/20 transition"
      />
    </div>
  )
}

function PasswordChecklist({ pw, confirm }: { pw: string; confirm: string }) {
  const checks = [
    { ok: pw.length >= 12, label: 'At least 12 characters' },
    { ok: /[A-Z]/.test(pw) && /[a-z]/.test(pw), label: 'Mix of upper and lower case' },
    { ok: /\d/.test(pw), label: 'At least one number' },
    { ok: pw.length > 0 && pw === confirm, label: 'Both passwords match' },
  ]
  return (
    <ul className="space-y-1 text-[12px]">
      {checks.map((c) => (
        <li key={c.label} className={`flex items-center gap-2 ${c.ok ? 'text-lc-white' : 'text-ink-400'}`}>
          <Check size={11} className={c.ok ? 'text-lc-red' : 'text-ink-500'} />
          {c.label}
        </li>
      ))}
    </ul>
  )
}
