'use client'
import { useEffect, useState } from 'react'
import { signIn } from 'next-auth/react'
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

export default function AuthCallbackPage() {
  const [status, setStatus] = useState('Completing sign-in...')
  const [error, setError] = useState('')
  const [diagnostic, setDiagnostic] = useState('')

  useEffect(() => {
    handleCallback()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleCallback() {
    try {
      const pca = new PublicClientApplication(msalConfig)
      await pca.initialize()

      const response = await pca.handleRedirectPromise({ navigateToLoginRequestUrl: false })

      if (!response || !response.idToken) {
        setError('No authentication response received. Please try again.')
        setDiagnostic('MSAL returned no idToken — likely the redirect was opened directly without an auth flow.')
        return
      }

      setStatus('Verifying account...')

      const ssoUrl = `${API_URL}/auth/sso`
      let res: Response
      try {
        res = await fetch(ssoUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_token: response.idToken }),
        })
      } catch (fetchErr: any) {
        setError('Could not reach the sign-in service.')
        setDiagnostic(`fetch(${ssoUrl}) threw: ${fetchErr?.message ?? String(fetchErr)}`)
        return
      }

      if (!res.ok) {
        const raw = await res.text()
        let detail = raw
        try {
          const parsed = JSON.parse(raw)
          detail = parsed?.detail || raw
        } catch {
          // not JSON — use raw text
        }
        setError(detail || `Sign-in service returned HTTP ${res.status}.`)
        setDiagnostic(`POST ${ssoUrl} → HTTP ${res.status}\nResponse: ${raw.slice(0, 500)}`)
        return
      }

      const data = await res.json()
      setStatus('Creating session...')

      const result = await signIn('sso-token', {
        token: data.access_token,
        callbackUrl: '/dashboard',
        redirect: false,
      })

      if (result?.error) {
        setError('Failed to create session.')
        setDiagnostic(`signIn returned error: ${result.error}`)
      } else if (result?.url) {
        window.location.href = result.url
      } else {
        window.location.href = '/dashboard'
      }
    } catch (err: any) {
      console.error('SSO callback error:', err)
      setError(err?.message || 'Authentication failed.')
      setDiagnostic(`Caught exception: ${err?.name ?? 'Error'}: ${err?.message ?? String(err)}\n${err?.stack ?? ''}`.slice(0, 800))
    }
  }

  return (
    <div className="min-h-screen bg-smoke flex items-center justify-center px-6 py-10">
      <div className="max-w-lg w-full">
        {error ? (
          <div className="text-center">
            <p className="lc-eyebrow mb-3">Sign-in failed</p>
            <p className="font-display text-2xl text-lc-black mb-2">Couldn&apos;t complete authentication.</p>
            <p className="text-sm text-ink-600 mb-4">{error}</p>
            {diagnostic && (
              <details className="text-left mt-4 mb-6 rounded-md border border-ink-200 bg-white">
                <summary className="cursor-pointer px-3 py-2 text-[11px] uppercase tracking-[0.16em] text-ink-500 font-bold">
                  Diagnostic details
                </summary>
                <pre className="px-3 py-2 text-[11px] text-ink-700 font-mono whitespace-pre-wrap break-words border-t border-ink-200">
                  {diagnostic}
                </pre>
              </details>
            )}
            <a
              href="/login"
              className="text-sm text-lc-red hover:underline underline-offset-2 font-medium"
            >
              Back to sign in
            </a>
          </div>
        ) : (
          <p className="text-center text-sm text-ink-500 animate-pulse-soft">{status}</p>
        )}
      </div>
    </div>
  )
}
