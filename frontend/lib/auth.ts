import NextAuth from 'next-auth'
import Credentials from 'next-auth/providers/credentials'

const API_URL = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function decodeJwtPayload(token: string): Record<string, unknown> {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(Buffer.from(base64, 'base64').toString('utf-8'))
  } catch {
    return {}
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    // Email + password login
    Credentials({
      id: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials): Promise<any> {
        const res = await fetch(`${API_URL}/auth/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({
            username: credentials?.email as string,
            password: credentials?.password as string,
          }),
        })
        if (!res.ok) return null
        const data = await res.json()
        const payload = decodeJwtPayload(data.access_token)
        const role = (payload.role as string) ?? 'client'
        return {
          id: data.access_token,
          accessToken: data.access_token,
          email: credentials?.email as string,
          role,
        }
      },
    }),
    // SSO login — frontend uses MSAL to get Azure ID token,
    // exchanges it for a backend JWT via /auth/sso, then passes it here.
    Credentials({
      id: 'sso-token',
      credentials: {
        token: { type: 'text' },
      },
      async authorize(credentials): Promise<any> {
        const token = credentials?.token as string
        if (!token) return null
        const payload = decodeJwtPayload(token)
        if (!payload.sub || !payload.exp) return null
        return {
          id: token,
          accessToken: token,
          email: (payload.email as string) ?? '',
          role: (payload.role as string) ?? 'client',
        }
      },
    }),
  ],
  callbacks: {
    jwt({ token, user, account }) {
      if (account && user) {
        token.accessToken = (user as any).accessToken
        token.role = (user as any).role
      }
      return token
    },
    session({ session, token }) {
      session.accessToken = token.accessToken as string
      if (session.user) {
        session.user.role = token.role as 'admin' | 'advisor' | 'client'
      }
      return session
    },
  },
  pages: { signIn: '/login' },
})
