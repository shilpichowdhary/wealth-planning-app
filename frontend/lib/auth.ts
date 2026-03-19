import NextAuth from 'next-auth'
import Credentials from 'next-auth/providers/credentials'

const API_URL = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
        return { id: data.access_token, accessToken: data.access_token, email: credentials?.email as string }
      },
    }),
  ],
  callbacks: {
    jwt({ token, user }) {
      if (user?.accessToken) token.accessToken = user.accessToken
      return token
    },
    session({ session, token }) {
      if (token.accessToken) session.accessToken = token.accessToken
      return session
    },
  },
  pages: { signIn: '/login' },
})
