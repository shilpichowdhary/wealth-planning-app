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
    Credentials({
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
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
  ],
  callbacks: {
    jwt({ token, user }) {
      if (user?.accessToken) token.accessToken = user.accessToken
      if (user?.role) token.role = user.role
      return token
    },
    session({ session, token }) {
      if (token.accessToken) session.accessToken = token.accessToken as string
      if (token.role) session.user = { ...session.user, role: token.role as string }
      return session
    },
  },
  pages: { signIn: '/login' },
})
