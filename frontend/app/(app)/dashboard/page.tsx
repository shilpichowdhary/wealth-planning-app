'use client'
import { useSession } from 'next-auth/react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowUpRight, Plus, Sparkles } from 'lucide-react'

interface CaseItem {
  case_id: string
  client_name: string
  last_updated: string
  status: string
  jurisdiction?: string
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
      .then(data => {
        setCases(data)
        setFetchError(null)
      })
      .catch(e => setFetchError(e.message))
      .finally(() => setLoading(false))
  }, [token, apiUrl, status])

  const activeCount = cases.filter(c => c.status === 'active').length

  return (
    <div className="max-w-[1280px] mx-auto w-full px-8 py-10">
      {/* Header */}
      <header className="mb-10 flex items-start justify-between gap-6 animate-fade-in-up">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-ink-500 font-medium">Workspace</p>
          <h1 className="mt-2 font-display text-[44px] leading-[1.05] tracking-tight text-ink-900">
            Cases
            <em className="italic text-brass-400 font-normal">.</em>
          </h1>
          <p className="mt-2 text-ink-600 text-[15px]">
            {cases.length > 0
              ? `${cases.length} total — ${activeCount} active`
              : 'Start by creating your first case.'}
          </p>
        </div>
        <Link
          href="/cases/new"
          className="lc-btn-primary"
        >
          <Plus size={16} />
          New case
        </Link>
      </header>

      {fetchError && (
        <div className="mb-6 rounded-lg border border-ember-500/40 bg-ember-500/10 px-4 py-3 text-sm text-ember-500 font-mono">
          {fetchError}
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-36 rounded-2xl border border-ink-200 bg-white animate-pulse-soft"
            />
          ))}
        </div>
      ) : cases.length === 0 && !fetchError ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cases.map((c, i) => (
            <Link
              key={c.case_id}
              href={`/cases/${c.case_id}`}
              style={{ animationDelay: `${i * 0.04}s` }}
              className="group relative overflow-hidden rounded-2xl border border-ink-200 bg-white p-5 hover:border-lc-red/50 hover:bg-ink-50 hover:-translate-y-0.5 transition-all animate-fade-in-up"
            >
              <div className="relative">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.16em] text-ink-500 font-medium mb-1">
                      Client
                    </div>
                    <h3 className="font-display text-lg font-semibold tracking-tight text-ink-900">
                      {c.client_name}
                    </h3>
                  </div>
                  <ArrowUpRight
                    size={16}
                    className="text-ink-400 group-hover:text-brass-400 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition"
                  />
                </div>
                <div className="mt-6 flex items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full border ${
                      c.status === 'active'
                        ? 'border-jade-500/40 bg-jade-500/10 text-jade-500'
                        : 'border-ink-300 bg-ink-50 text-ink-500'
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        c.status === 'active' ? 'bg-jade-500 animate-pulse-soft' : 'bg-ink-500'
                      }`}
                    />
                    {c.status}
                  </span>
                  <span className="text-[11px] text-ink-500">
                    Updated {new Date(c.last_updated).toLocaleDateString(undefined, {
                      day: 'numeric',
                      month: 'short',
                    })}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="rounded-2xl border border-dashed border-ink-300 bg-ink-50 p-12 text-center animate-fade-in-up">
      <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-brass-500/10 border border-brass-500/30 mb-4">
        <Sparkles size={20} className="text-brass-400" />
      </div>
      <h3 className="font-display text-xl font-semibold text-ink-900">No cases yet</h3>
      <p className="mt-2 text-sm text-ink-600 max-w-sm mx-auto">
        Create a case to start a private advisory dialogue. Each case remembers prior conversations and structures you build.
      </p>
      <Link
        href="/cases/new"
        className="lc-btn-primary mt-6"
      >
        <Plus size={16} />
        Create your first case
      </Link>
    </div>
  )
}
