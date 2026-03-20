'use client'
import { useSession } from 'next-auth/react'
import { useEffect, useState } from 'react'
import Link from 'next/link'

interface CaseItem {
  case_id: string
  client_name: string
  last_updated: string
  status: string
}

export default function DashboardPage() {
  const { data: session, status } = useSession()
  const token = session?.accessToken ?? ''
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  const [cases, setCases] = useState<CaseItem[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)

  useEffect(() => {
    if (status === 'loading') return
    if (!token) {
      setLoading(false)
      setFetchError(`No token — session status: ${status}`)
      return
    }
    fetch(`${apiUrl}/cases/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async r => {
        if (!r.ok) {
          const body = await r.text()
          throw new Error(`${r.status}: ${body}`)
        }
        return r.json()
      })
      .then(data => { setCases(data); setFetchError(null) })
      .catch(e => setFetchError(e.message))
      .finally(() => setLoading(false))
  }, [token, apiUrl, status])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Cases</h1>
        <Link href="/cases/new" className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition">
          + New Case
        </Link>
      </div>

      {fetchError && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 font-mono">
          {fetchError}
        </div>
      )}

      {loading ? (
        <p className="text-slate-400 text-sm">Loading cases...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cases.map((c) => (
            <Link key={c.case_id} href={`/cases/${c.case_id}`}
              className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition block">
              <h3 className="font-semibold text-slate-900">{c.client_name}</h3>
              <p className="text-slate-500 text-xs mt-1">{new Date(c.last_updated).toLocaleDateString()}</p>
              <span className={`inline-block mt-2 text-xs px-2 py-0.5 rounded-full ${
                c.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
              }`}>
                {c.status}
              </span>
            </Link>
          ))}
          {!loading && cases.length === 0 && !fetchError && (
            <p className="text-slate-500 text-sm col-span-3">No cases yet. Create your first case.</p>
          )}
        </div>
      )}
    </div>
  )
}
