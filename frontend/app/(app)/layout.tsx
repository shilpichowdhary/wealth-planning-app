import { auth } from '@/lib/auth'
import { redirect } from 'next/navigation'
import Link from 'next/link'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth()
  if (!session) redirect('/login')
  const role = (session.user as any)?.role
  const isAdvisor = role === 'advisor' || role === 'admin'
  const isAdmin = role === 'admin'

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="bg-slate-900 text-white px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/dashboard" className="font-semibold text-sm tracking-wide hover:text-slate-300 transition">
            Wealth Planning Advisor
          </Link>
          <div className="flex items-center gap-4 text-sm text-slate-300">
            <Link href="/dashboard" className="hover:text-white transition">Cases</Link>
            <Link href="/cases/new" className="hover:text-white transition">+ New Case</Link>
            {isAdvisor && (
              <>
                <Link href="/kb/documents" className="hover:text-white transition">KB Documents</Link>
                <Link href="/kb/upload" className="hover:text-white transition">Upload KB</Link>
                <Link href="/kb/review" className="hover:text-white transition">KB Review</Link>
              </>
            )}
            {isAdmin && (
              <Link href="/admin/advisors" className="hover:text-white transition text-amber-400 font-medium">
                Admin
              </Link>
            )}
          </div>
        </div>
        <span className="text-slate-400 text-xs">{session.user?.email}</span>
      </nav>
      <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
    </div>
  )
}
