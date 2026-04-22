'use client'
import { Suspense, useState, useEffect, useRef } from 'react'
import { signIn } from 'next-auth/react'
import { useRouter, useSearchParams } from 'next/navigation'
import { PublicClientApplication, type Configuration } from '@azure/msal-browser'
import { LCLogoMark, LCWordmark } from '@/components/brand/LCLogo'

const AZURE_CLIENT_ID = process.env.NEXT_PUBLIC_AZURE_CLIENT_ID || ''
const AZURE_TENANT_ID = process.env.NEXT_PUBLIC_AZURE_TENANT_ID || ''

const msalConfig: Configuration = {
  auth: {
    clientId: AZURE_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${AZURE_TENANT_ID}`,
    redirectUri: `${typeof window !== 'undefined' ? window.location.origin : ''}/users/microsoft/callback`,
  },
  cache: {
    cacheLocation: 'sessionStorage',
  },
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}

function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [ssoLoading, setSsoLoading] = useState(false)
  const msalRef = useRef<PublicClientApplication | null>(null)
  const router = useRouter()
  const searchParams = useSearchParams()

  const ssoError = searchParams.get('error')

  useEffect(() => {
    if (AZURE_CLIENT_ID) {
      const pca = new PublicClientApplication(msalConfig)
      pca.initialize().then(() => {
        pca.handleRedirectPromise().catch(() => {})
        msalRef.current = pca
      })
    }
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    const result = await signIn('credentials', { email, password, redirect: false })
    setLoading(false)
    if (result?.error) setError('Invalid email or password')
    else router.push('/dashboard')
  }

  async function handleSSO() {
    if (!msalRef.current) {
      setError('SSO is not configured.')
      return
    }
    setSsoLoading(true)
    setError('')
    await msalRef.current.loginRedirect({
      scopes: ['openid', 'profile', 'email', 'User.Read'],
    })
  }

  const displayError = error || (ssoError === 'OAuthCallbackError' ? 'SSO authentication failed.' : '')
  const ssoEnabled = Boolean(AZURE_CLIENT_ID)

  return (
    <div className="min-h-screen bg-lc-black flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-[1080px] grid grid-cols-1 lg:grid-cols-[1.15fr_1fr] gap-16 items-center">
        {/* Editorial left panel */}
        <div className="hidden lg:block animate-fade-in-up">
          <div className="flex items-center gap-3 mb-10">
            <LCLogoMark size={36} />
            <LCWordmark className="text-lc-white" />
          </div>

          <h1 className="font-display text-[64px] leading-[1.04] text-lc-white text-balance">
            Private wealth planning,
            <br />
            with <span className="text-lc-red">institutional</span> depth.
          </h1>
          <p className="mt-6 text-ink-300 text-[15px] leading-relaxed max-w-md text-pretty">
            Research, draft, and reason across seven jurisdictions — with a knowledge base purpose-built for
            Lighthouse Canton advisors.
          </p>

          <div className="mt-10 flex flex-wrap gap-2">
            {['India', 'Singapore', 'UAE', 'USA', 'UK', 'Taiwan', 'China', 'Cross-border'].map(j => (
              <span key={j} className="chip">{j}</span>
            ))}
          </div>
        </div>

        {/* Auth card */}
        <div className="animate-fade-in-up" style={{ animationDelay: '0.08s' }}>
          <div className="rounded-2xl bg-ink-900 border border-ink-800 p-8">
            <h2 className="font-display text-2xl text-lc-white">Sign in</h2>
            <p className="mt-1 text-sm text-ink-400">Use your Lighthouse Canton credentials.</p>

            {ssoEnabled && (
              <>
                <button
                  type="button"
                  onClick={handleSSO}
                  disabled={ssoLoading}
                  className="mt-6 w-full rounded-lg bg-lc-white text-lc-black py-3 text-sm font-bold tracking-wide hover:bg-ink-100 transition disabled:opacity-50"
                >
                  {ssoLoading ? 'Redirecting…' : 'Sign in with LC Account'}
                </button>
                <div className="flex items-center gap-3 my-5">
                  <div className="flex-1 h-px bg-ink-800" />
                  <span className="text-[10px] uppercase tracking-[0.18em] text-ink-500">or email & password</span>
                  <div className="flex-1 h-px bg-ink-800" />
                </div>
              </>
            )}

            <form onSubmit={handleSubmit} className={`${ssoEnabled ? '' : 'mt-7'} space-y-4`}>
              <Field label="Email">
                <input
                  type="email"
                  placeholder="you@lighthouse-canton.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full bg-ink-850 border border-ink-700 rounded-lg px-4 py-3 text-[15px] text-lc-white placeholder:text-ink-500 focus:outline-none focus:border-lc-red focus:ring-2 focus:ring-lc-red/20 transition"
                  required
                />
              </Field>
              <Field label="Password">
                <input
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full bg-ink-850 border border-ink-700 rounded-lg px-4 py-3 text-[15px] text-lc-white placeholder:text-ink-500 focus:outline-none focus:border-lc-red focus:ring-2 focus:ring-lc-red/20 transition"
                  required
                />
              </Field>
              {displayError && (
                <div className="rounded-lg border border-lc-red bg-lc-red/10 px-3 py-2 text-sm text-lc-red">
                  {displayError}
                </div>
              )}
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg bg-lc-red text-lc-white py-3 text-sm font-bold tracking-wide hover:bg-lc-red/90 transition disabled:opacity-50"
              >
                {loading ? 'Signing in…' : 'Continue'}
              </button>
            </form>

            <p className="mt-6 text-[11px] text-ink-400 leading-relaxed">
              Internal use only. Anonymise client data before sharing queries.
            </p>
          </div>
          <p className="mt-3 text-center text-[10px] uppercase tracking-[0.2em] text-ink-500">
            lighthouse-canton.com
          </p>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-[0.16em] text-ink-300 font-bold mb-1.5">
        {label}
      </label>
      {children}
    </div>
  )
}
