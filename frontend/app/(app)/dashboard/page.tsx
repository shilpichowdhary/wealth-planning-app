import { auth } from '@/lib/auth'
import { apiFetch } from '@/lib/api-client'
import Link from 'next/link'

export default async function DashboardPage() {
  const session = await auth()
  const token = (session as any)?.accessToken as string
  const cases = await apiFetch<any[]>('/cases/', token).catch(() => [])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Cases</h1>
        <Link href="/cases/new" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition">
          + New Case
        </Link>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {cases.map((c: any) => (
          <Link key={c.case_id} href={`/cases/${c.case_id}`}
            className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition block">
            <h3 className="font-semibold text-slate-900">{c.client_name}</h3>
            <p className="text-slate-500 text-xs mt-1">{new Date(c.last_updated).toLocaleDateString()}</p>
            <span className={`inline-block mt-2 text-xs px-2 py-0.5 rounded-full ${c.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
              {c.status}
            </span>
          </Link>
        ))}
        {cases.length === 0 && (
          <p className="text-slate-500 text-sm col-span-3">No cases yet. Create your first case.</p>
        )}
      </div>
    </div>
  )
}
