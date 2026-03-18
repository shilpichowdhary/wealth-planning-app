import { auth } from '@/lib/auth'
import { redirect } from 'next/navigation'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth()
  if (!session) redirect('/login')
  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="bg-slate-900 text-white px-6 py-3 flex items-center justify-between">
        <span className="font-semibold text-sm tracking-wide">Wealth Planning Advisor</span>
        <span className="text-slate-400 text-xs">{session.user?.email}</span>
      </nav>
      <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
    </div>
  )
}
