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

  useEffect(() => {
    handleCallback()
  }, [])

  async function handleCallback() {
    try {
      const pca = new PublicClientApplication(msalConfig)
      await pca.initialize()

      const response = await pca.handleRedirectPromise({ navigateToLoginRequestUrl: false })

      if (!response || !response.idToken) {
        setError('No authentication response received. Please try again.')
        return
      }

      setStatus('Verifying account...')

      const res = await fetch(`${API_URL}/auth/sso`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_token: response.idToken }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'SSO login failed.')
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
      } else if (result?.url) {
        window.location.href = result.url
      } else {
        window.location.href = '/dashboard'
      }
    } catch (err: any) {
      console.error('SSO callback error:', err)
      setError(err?.message || 'Authentication failed.')
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center">
        {error ? (
          <div>
            <p className="text-red-400 text-sm mb-4">{error}</p>
            <a href="/login" className="text-blue-400 text-sm hover:underline">
              Back to login
            </a>
          </div>
        ) : (
          <p className="text-slate-400 text-sm">{status}</p>
        )}
      </div>
    </div>
  )
}
