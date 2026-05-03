'use client'
import { Suspense, useState, useEffect, useRef } from 'react'
import { signIn } from 'next-auth/react'
import { useRouter, useSearchParams } from 'next/navigation'
import { PublicClientApplication, type Configuration } from '@azure/msal-browser'

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
  const [showPasswordForm, setShowPasswordForm] = useState(false)
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
    <div className="login-grid">
      {/* Editorial column ------------------------------------------------ */}
      <div className="login-editorial">
        <div className="login-editorial__bg" />
        <svg className="login-editorial__grid" width="100%" height="100%" aria-hidden>
          <defs>
            <pattern id="editorial-grid" width="88" height="88" patternUnits="userSpaceOnUse">
              <path d="M88 0H0V88" fill="none" stroke="#ffffff" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#editorial-grid)" />
        </svg>

        {/* Brand top-left */}
        <div className="login-brand">
          <BrandMark />
          <div className="login-brand__name">Lighthouse Canton</div>
        </div>

        {/* Vertically centred centrepiece — order is product → rule → headline. */}
        <div className="login-editorial__hero">
          <div className="login-editorial__product">Wealth Planning Console</div>
          <div className="login-editorial__rule" />
          <div className="login-editorial__headline">
            Private wealth planning, with <em>institutional</em> depth across seven jurisdictions.
          </div>
          <div className="login-editorial__sub">
            Research, draft, and reason against a knowledge base purpose-built for Lighthouse Canton
            advisors. Every recommendation grounded in firm-approved sources.
          </div>
        </div>

        <div className="login-editorial__footer">
          <div className="login-editorial__regulators">
            <span className="label">Regulated by</span>
            <div className="badge">MAS</div>
            <div className="badge">DFSA</div>
            <div className="badge">SEBI</div>
            <div className="badge">FCA</div>
          </div>
          <div className="login-editorial__ver">Wealth Planning · Apr 2026</div>
        </div>
      </div>

      {/* Sign-in column -------------------------------------------------- */}
      <div className="login-signin">
        <div className="login-signin__body">
          <div className="login-eyebrow">Secure access · Single sign-on</div>
          <h1 className="login-h1">Sign in</h1>
          <p className="login-lead">
            Use your Lighthouse Canton Microsoft account. Wealth Planning inherits your firm roles
            and entity access automatically.
          </p>

          {displayError && (
            <div
              className="mb-4 px-3 py-2 text-[13px] border-l-[3px]"
              style={{ background: '#fdecec', color: '#8a1b1b', borderColor: '#c62828' }}
            >
              {displayError}
            </div>
          )}

          {ssoEnabled ? (
            <button
              type="button"
              onClick={handleSSO}
              disabled={ssoLoading}
              className="login-sso"
            >
              <svg width="19" height="19" viewBox="0 0 23 23" aria-hidden>
                <rect x="1" y="1" width="10" height="10" fill="#F25022" />
                <rect x="12" y="1" width="10" height="10" fill="#7FBA00" />
                <rect x="1" y="12" width="10" height="10" fill="#00A4EF" />
                <rect x="12" y="12" width="10" height="10" fill="#FFB900" />
              </svg>
              <span>{ssoLoading ? 'Redirecting…' : 'Continue with LC Account'}</span>
              <svg
                width="16"
                height="16"
                viewBox="0 0 14 14"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                aria-hidden
                style={{ marginLeft: 4 }}
              >
                <path d="M3 7h8M7 3l4 4-4 4" />
              </svg>
            </button>
          ) : null}

          {/* Password fallback — secondary, disclosure-style. Hidden behind a
              link so the SSO CTA remains the only visible primary action. */}
          {!showPasswordForm ? (
            <button
              type="button"
              onClick={() => setShowPasswordForm(true)}
              className="mt-6 text-[12px] text-ink-500 hover:text-lc-black underline-offset-2 hover:underline self-start"
            >
              Sign in with email &amp; password instead
            </button>
          ) : (
            <form onSubmit={handleSubmit} className="mt-8 space-y-3">
              <div>
                <label className="block text-[11px] uppercase tracking-[0.16em] text-ink-600 font-bold mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  placeholder="you@lighthouse-canton.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full bg-white border border-ink-300 px-3 py-2.5 text-[14px] text-lc-black placeholder:text-ink-400 focus:outline-none focus:border-lc-red focus:ring-2 focus:ring-lc-red/20 transition"
                  required
                />
              </div>
              <div>
                <label className="block text-[11px] uppercase tracking-[0.16em] text-ink-600 font-bold mb-1.5">
                  Password
                </label>
                <input
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full bg-white border border-ink-300 px-3 py-2.5 text-[14px] text-lc-black placeholder:text-ink-400 focus:outline-none focus:border-lc-red focus:ring-2 focus:ring-lc-red/20 transition"
                  required
                />
              </div>
              <div className="flex items-center justify-between gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => setShowPasswordForm(false)}
                  className="text-[12px] text-ink-500 hover:text-lc-black"
                >
                  ← Back to SSO
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="lc-btn-primary"
                >
                  {loading ? 'Signing in…' : 'Continue'}
                </button>
              </div>
            </form>
          )}
        </div>

        <div className="login-signin__footer">
          <div>
            Trouble signing in? <a href="mailto:ai_lab@lighthouse-canton.com">AI Lab Support</a>
          </div>
          <div className="copy">© 2026 Lighthouse Canton</div>
        </div>
      </div>
    </div>
  )
}

/**
 * 44×44 crimson square with a white serif "L" — DCMS canonical brand mark
 * for the login screen. Larger than the in-app sidebar mark.
 */
function BrandMark() {
  return (
    <span
      role="img"
      aria-label="Lighthouse Canton"
      style={{
        width: 44,
        height: 44,
        background: '#E50025',
        color: '#fff',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'var(--font-display)',
        fontSize: 24,
        fontWeight: 500,
        lineHeight: 1,
        flexShrink: 0,
      }}
    >
      L
    </span>
  )
}
