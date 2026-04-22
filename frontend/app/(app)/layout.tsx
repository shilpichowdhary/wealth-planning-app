import { auth } from '@/lib/auth'
import { redirect } from 'next/navigation'
import Sidebar from '@/components/shell/Sidebar'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth()
  if (!session) redirect('/login')
  const role = (session.user as any)?.role ?? 'advisor'
  const email = session.user?.email ?? ''
  const name = (session.user as any)?.name ?? email.split('@')[0]

  return (
    <div className="min-h-screen bg-ink-950 text-ink-100 flex">
      <Sidebar role={role} name={name} email={email} />
      <main className="flex-1 min-w-0 flex flex-col">
        {children}
      </main>
    </div>
  )
}
