'use client'
import { Suspense, useState, useEffect, useRef } from 'react'
import { signIn } from 'next-auth/react'
import { useRouter, useSearchParams } from 'next/navigation'
import { PublicClientApplication, type Configuration } from '@azure/msal-browser'

const AZURE_CLIENT_ID = process.env.NEXT_PUBLIC_AZURE_CLIENT_ID || ''
const AZURE_TENANT_ID = process.env.NEXT_PUBLIC_AZURE_TENANT_ID || ''
const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

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
        // Clear any stale interaction state before allowing new logins
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
    // Redirect to Microsoft login — callback page handles the response
    await msalRef.current.loginRedirect({
      scopes: ['openid', 'profile', 'email', 'User.Read'],
    })
  }

  const displayError = error || (ssoError === 'OAuthCallbackError' ? 'SSO authentication failed.' : '')

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-lg p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Wealth Planning Advisor</h1>
        <p className="text-slate-500 mb-6 text-sm">Sign in to your account</p>

        {/* SSO Button */}
        <button
          onClick={handleSSO}
          disabled={ssoLoading}
          className="w-full bg-slate-900 text-white rounded-lg py-2.5 text-sm font-semibold hover:bg-slate-800 transition disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {ssoLoading ? 'Signing in...' : 'Sign in using LC Account'}
        </button>

        {/* Divider */}
        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 h-px bg-slate-200" />
          <span className="text-xs text-slate-400">or use email & password</span>
          <div className="flex-1 h-px bg-slate-200" />
        </div>

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <input
            type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          {displayError && <p className="text-red-500 text-sm">{displayError}</p>}
          <button type="submit" disabled={loading}
            className="w-full bg-blue-600 text-white rounded-lg py-2.5 text-sm font-semibold hover:bg-blue-700 transition disabled:opacity-50">
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
