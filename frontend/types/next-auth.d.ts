import 'next-auth'
import 'next-auth/jwt'

declare module 'next-auth' {
  interface Session {
    accessToken?: string
    user?: {
      name?: string | null
      email?: string | null
      image?: string | null
      role?: 'advisor' | 'client'
    }
  }
  interface User {
    accessToken?: string
    role?: 'advisor' | 'client'
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    accessToken?: string
    role?: 'advisor' | 'client'
  }
}
