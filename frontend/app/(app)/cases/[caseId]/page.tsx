'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { DiagramPanel } from '@/components/diagram/DiagramPanel'
import { createSSEStream, type KbInsufficientEvent } from '@/lib/sse-client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  MessageSquareText,
  Network,
  Download,
  Sparkles,
  Send,
  Brain,
  AlertTriangle,
  Globe,
  BookOpenText,
  X,
  FileText,
  Presentation,
  RefreshCw,
  Loader2,
} from 'lucide-react'

type DeckState =
  | { status: 'loading' }
  | { status: 'none' }
  | {
      status: 'ready'
      version: number
      generated_at: string
      generated_by?: string | null
      model_used?: string | null
      stale: boolean
      has_pdf: boolean
    }

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: any
}

interface CaseData {
  case_id: string
  client_name: string
  status: string
  last_updated: string
}

export default function CasePage({ params }: { params: { caseId: string } }) {
  const caseId = params.caseId
  const { data: session } = useSession()
  const token = session?.accessToken ?? ''

  const [caseData, setCaseData] = useState<CaseData | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const [hasPriorMemory, setHasPriorMemory] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [existingDiagram, setExistingDiagram] = useState<{ nodes: any[]; edges: any[] } | null>(null)
  const [recommendedDiagram, setRecommendedDiagram] = useState<{ nodes: any[]; edges: any[] } | null>(null)
  const [activeTab, setActiveTab] = useState<'chat' | 'diagram'>('chat')
  // KB-first gate: when the backend says KB is thin, we pause the stream
  // and show a modal so the advisor can decide whether to allow web search.
  const [kbPrompt, setKbPrompt] = useState<KbInsufficientEvent | null>(null)
  const [tavilyCount, setTavilyCount] = useState(0)
  const [diagramSavedAt, setDiagramSavedAt] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [deck, setDeck] = useState<DeckState>({ status: 'loading' })
  const [generatingDeck, setGeneratingDeck] = useState(false)
  const [deckError, setDeckError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<(() => void) | null>(null)
  // Mirror existingDiagram into a ref so the SSE callback (whose closure may
  // be stale by the time the diagram event arrives) can branch on the latest
  // value rather than the snapshot at sendMessage creation time.
  const existingDiagramRef = useRef<{ nodes: any[]; edges: any[] } | null>(null)
  useEffect(() => {
    existingDiagramRef.current = existingDiagram
  }, [existingDiagram])
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current()
    }
  }, [])

  useEffect(() => {
    if (!token) return
    fetch(`${apiUrl}/cases/${caseId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (data) setCaseData(data)
      })
      .catch(() => {})

    Promise.all([
      fetch(`${apiUrl}/cases/${caseId}/history`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => (r.ok ? r.json() : [])),
      fetch(`${apiUrl}/cases/${caseId}/summary`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => (r.ok ? r.json() : { summary: '' })),
      fetch(`${apiUrl}/cases/${caseId}/diagram`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => (r.ok ? r.json() : { nodes: [], edges: [], updated_at: null })),
    ])
      .then(([history, summaryData, diagramData]) => {
        const msgs: Message[] = history.map((h: any) => ({
          id: crypto.randomUUID(),
          role: h.role,
          content: h.content,
          sources: h.sources,
        }))
        setMessages(msgs)
        if (summaryData.summary) setHasPriorMemory(true)
        if (diagramData?.nodes?.length) {
          setExistingDiagram({ nodes: diagramData.nodes, edges: diagramData.edges ?? [] })
          setDiagramSavedAt(diagramData.updated_at ?? null)
        }
      })
      .catch(() => {})
      .finally(() => setHistoryLoading(false))
  }, [caseId, token, apiUrl])

  const saveDiagram = useCallback(
    async (nodes: any[], edges: any[]) => {
      setSaveError(null)
      try {
        const res = await fetch(`${apiUrl}/cases/${caseId}/diagram`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ nodes, edges }),
        })
        if (!res.ok) {
          const body = await res.text()
          throw new Error(`${res.status}: ${body}`)
        }
        const data = await res.json()
        setExistingDiagram({ nodes: data.nodes, edges: data.edges })
        setDiagramSavedAt(data.updated_at ?? null)
      } catch (e: any) {
        setSaveError(e?.message ?? 'Save failed')
        throw e
      }
    },
    [apiUrl, caseId, token],
  )

  const sendMessage = useCallback(
    (opts?: { allowWeb?: boolean; forceAnswer?: boolean; resendQuery?: string }) => {
      const userMsg = opts?.resendQuery ?? input.trim()
      if (!userMsg || streaming || !token) return

      const isResend = !!opts?.resendQuery
      if (!isResend) setInput('')
      if (!isResend) {
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', content: userMsg }])
      }
      setStreaming(true)
      setChatError(null)
      setKbPrompt(null)

      let assistantContent = ''
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: '' }])

      const allowWeb = opts?.allowWeb ?? false
      const forceAnswer = opts?.forceAnswer ?? false

      const abort = createSSEStream(
        `${apiUrl}/chat/stream`,
        token,
        {
          message: userMsg,
          case_id: caseId,
          session_tavily_count: tavilyCount,
          allow_web: allowWeb,
          force_answer: forceAnswer,
        },
        text => {
          assistantContent += text
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1] = { ...updated[updated.length - 1], content: assistantContent }
            return updated
          })
        },
        sourcesData => {
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              sources: sourcesData.sources,
            }
            return updated
          })
          if (sourcesData.existing_diagram) setExistingDiagram(sourcesData.existing_diagram)
          if (sourcesData.recommended_diagram) setRecommendedDiagram(sourcesData.recommended_diagram)
          if (allowWeb && (sourcesData.web?.length ?? 0) > 0) {
            setTavilyCount(c => c + 1)
          }
        },
        () => {
          setStreaming(false)
          abortRef.current = null
        },
        diagramData => {
          // Diagram arrives via the LLM tool call — chat content is already
          // pure markdown. The backend auto-persists the proposal when no
          // existing diagram exists for the case (see chat.py). Mirror that
          // here: if the case had no saved diagram, treat the proposal as
          // the new "existing" so the diagram tab shows it as the canonical
          // structure rather than as a transient recommendation. Otherwise
          // route into recommendedDiagram for side-by-side comparison.
          if (!existingDiagramRef.current) {
            setExistingDiagram(diagramData)
            setDiagramSavedAt(new Date().toISOString())
          } else {
            setRecommendedDiagram(diagramData)
          }
        },
        errMsg => {
          setChatError(errMsg)
          setStreaming(false)
        },
        // KB-insufficient: drop the placeholder assistant bubble and show the
        // permission modal. Nothing is streamed — the advisor decides.
        evt => {
          setMessages(prev => prev.slice(0, -1))
          setKbPrompt(evt)
          setStreaming(false)
        },
      )

      abortRef.current = abort
    },
    [input, streaming, token, caseId, apiUrl, tavilyCount],
  )

  const fetchDeckStatus = useCallback(async () => {
    if (!token) return
    try {
      const res = await fetch(`${apiUrl}/reports/${caseId}/deck`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        setDeck({ status: 'none' })
        return
      }
      const d = await res.json()
      setDeck(d.exists ? { status: 'ready', ...d } : { status: 'none' })
    } catch {
      setDeck({ status: 'none' })
    }
  }, [apiUrl, caseId, token])

  // Pull initial deck status when the case loads
  useEffect(() => {
    fetchDeckStatus()
  }, [fetchDeckStatus])

  async function generateDeck() {
    setGeneratingDeck(true)
    setDeckError(null)
    try {
      const res = await fetch(`${apiUrl}/reports/${caseId}/deck/generate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `Generate failed (${res.status})`)
      }
      await fetchDeckStatus()
    } catch (e: any) {
      setDeckError(String(e?.message ?? e))
    } finally {
      setGeneratingDeck(false)
    }
  }

  async function downloadDeck(kind: 'pptx' | 'pdf') {
    const ext = kind
    const res = await fetch(`${apiUrl}/reports/${caseId}/deck.${ext}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) {
      setDeckError(`Download failed (${res.status})`)
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const safeName = (caseData?.client_name || caseId.slice(0, 8)).replace(/[^A-Za-z0-9_-]/g, '_')
    a.download = `wealth-plan-${safeName}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
    // PDF state may flip to has_pdf=true after first download — refetch status
    if (kind === 'pdf') fetchDeckStatus()
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex-1 flex flex-col h-screen max-h-screen min-h-0">
      {/* Header */}
      <header className="border-b border-ink-200 bg-white/40 backdrop-blur sticky top-0 z-10">
        <div className="px-8 py-5 flex items-center justify-between gap-6">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.2em] text-ink-500 font-medium">Case</p>
            <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-ink-900 truncate">
              {caseData?.client_name || 'Loading…'}
            </h1>
            <p className="mt-0.5 text-[11px] text-ink-400 font-mono">{caseId.slice(0, 8)}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-ink-300 overflow-hidden bg-white">
              <button
                onClick={() => setActiveTab('chat')}
                className={`flex items-center gap-2 px-3.5 py-2 text-sm font-medium transition ${
                  activeTab === 'chat'
                    ? 'bg-ink-100 text-ink-900'
                    : 'text-ink-600 hover:bg-ink-50 hover:text-ink-900'
                }`}
              >
                <MessageSquareText size={14} />
                Chat
              </button>
              <button
                onClick={() => setActiveTab('diagram')}
                className={`flex items-center gap-2 px-3.5 py-2 text-sm font-medium transition border-l border-ink-300 ${
                  activeTab === 'diagram'
                    ? 'bg-ink-100 text-ink-900'
                    : 'text-ink-600 hover:bg-ink-50 hover:text-ink-900'
                }`}
              >
                <Network size={14} />
                Structure
                {recommendedDiagram && (
                  <span className="ml-1 h-1.5 w-1.5 rounded-full bg-brass-500 animate-pulse-soft" />
                )}
              </button>
            </div>
            {/* Deck controls: Generate when none, dual-download + regen when ready */}
            {deck.status === 'loading' || generatingDeck ? (
              <button
                disabled
                className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium bg-white border border-ink-300 text-ink-500 rounded-lg cursor-default"
              >
                <Loader2 size={14} className="animate-spin" />
                {generatingDeck ? 'Generating deck…' : 'Loading…'}
              </button>
            ) : deck.status === 'none' ? (
              <button
                onClick={generateDeck}
                className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium bg-lc-black text-white border border-lc-black rounded-lg hover:bg-ink-800 transition"
                title="Use Claude to compose an LC-branded slide deck from this case"
              >
                <Sparkles size={14} />
                Generate deck
              </button>
            ) : (
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => downloadDeck('pptx')}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium bg-white border border-ink-300 text-ink-900 rounded-lg hover:bg-ink-50 transition"
                  title={`Editable PowerPoint (v${deck.version})`}
                >
                  <Presentation size={14} />
                  PPTX
                </button>
                <button
                  onClick={() => downloadDeck('pdf')}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium bg-white border border-ink-300 text-ink-900 rounded-lg hover:bg-ink-50 transition"
                  title={`PDF export (v${deck.version})`}
                >
                  <FileText size={14} />
                  PDF
                </button>
                <button
                  onClick={generateDeck}
                  className={`flex items-center gap-1.5 px-2.5 py-2 text-sm font-medium border rounded-lg transition ${
                    deck.stale
                      ? 'bg-brass-50 border-brass-300 text-brass-800 hover:bg-brass-100'
                      : 'bg-white border-ink-300 text-ink-600 hover:bg-ink-50'
                  }`}
                  title={
                    deck.stale
                      ? 'Inputs changed since last generation — regenerate'
                      : `Regenerate deck (current: v${deck.version})`
                  }
                >
                  <RefreshCw size={14} />
                  {deck.stale ? 'Outdated' : 'v' + deck.version}
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Deck error toast — slides down from header on failure */}
      {deckError && (
        <div className="absolute top-20 right-6 z-20 max-w-md rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800 shadow-md">
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="font-medium">Deck generation failed</p>
              <p className="mt-0.5 text-xs text-rose-700/80">{deckError}</p>
            </div>
            <button onClick={() => setDeckError(null)} className="text-rose-500 hover:text-rose-700">
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {activeTab === 'chat' ? (
          <div className="h-full flex flex-col">
            {/* Memory banner */}
            {hasPriorMemory && (
              <div className="mx-8 mt-4 flex items-center gap-2.5 rounded-lg border border-brass-500/30 bg-brass-500/[0.06] px-4 py-2.5 text-[13px] text-brass-300">
                <Brain size={14} />
                <span>
                  <strong className="text-brass-300 font-semibold">Session memory active</strong>
                  <span className="text-ink-600"> — context from previous conversations on this case is loaded.</span>
                </span>
              </div>
            )}

            {/* Messages scroll */}
            <div className="flex-1 overflow-y-auto">
              <div className="max-w-[860px] mx-auto px-8 py-8 space-y-6">
                {historyLoading ? (
                  <CenteredMessage text="Loading conversation history…" />
                ) : messages.length === 0 ? (
                  <WelcomePrompt onSuggest={s => setInput(s)} />
                ) : null}

                {messages.map(msg => (
                  <div
                    key={msg.id}
                    className={`flex animate-fade-in-up ${
                      msg.role === 'user' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    {msg.role === 'user' ? (
                      <div className="max-w-[70%] rounded-2xl rounded-br-sm bg-brass-500/[0.08] border border-brass-500/20 px-4 py-3 text-[15px] text-ink-900 leading-relaxed">
                        {msg.content}
                      </div>
                    ) : (
                      <div className="w-full">
                        <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-ink-500 font-medium">
                          <Sparkles size={11} className="text-brass-400" />
                          Advisor
                        </div>
                        {msg.content ? (
                          <div className="prose-chat">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                          </div>
                        ) : streaming && msg.id === messages[messages.length - 1]?.id ? (
                          <ThinkingDots />
                        ) : null}
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="mt-4 pt-4 border-t border-ink-200">
                            <p className="text-[11px] uppercase tracking-[0.16em] text-ink-500 font-medium mb-2">Sources</p>
                            <div className="flex flex-wrap gap-1.5">
                              {msg.sources.slice(0, 8).map((s: any, si: number) => (
                                <span key={si} className="chip">
                                  {s.source_file || s.title || `Source ${si + 1}`}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Composer */}
            <div className="border-t border-ink-200 bg-white/40 backdrop-blur">
              <div className="max-w-[860px] mx-auto px-8 py-5">
                {chatError && (
                  <div className="mb-3 flex items-center gap-2 rounded-lg border border-ember-500/40 bg-ember-500/10 px-3 py-2 text-sm text-ember-500">
                    <AlertTriangle size={14} />
                    {chatError}
                  </div>
                )}
                <div className="relative rounded-2xl border border-ink-300 bg-ink-50 focus-within:border-lc-red/60 focus-within:ring-2 focus-within:ring-lc-red/20 transition">
                  <textarea
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about tax optimisation, succession, structures…  (⏎ to send, ⇧⏎ newline)"
                    rows={2}
                    disabled={streaming}
                    className="w-full bg-transparent px-4 py-3.5 text-[15px] text-lc-black placeholder:text-ink-400 focus:outline-none resize-none disabled:opacity-50 pr-14"
                  />
                  <button
                    onClick={() => sendMessage()}
                    disabled={streaming || !input.trim()}
                    className="absolute bottom-2.5 right-2.5 inline-flex h-9 w-9 items-center justify-center rounded-lg bg-lc-black text-lc-white hover:bg-ink-700 transition disabled:opacity-40 disabled:cursor-not-allowed"
                    title="Send (Enter)"
                  >
                    <Send size={14} />
                  </button>
                </div>
                <div className="mt-2 flex items-center gap-2 text-[11px] text-ink-500">
                  <BookOpenText size={11} />
                  <span>KB-first · web search requires your approval</span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full bg-smoke">
            {saveError && (
              <div className="px-4 py-2 text-[12px] text-lc-red border-b border-lc-red/40 bg-lc-red/5">
                Save failed: {saveError}
              </div>
            )}
            <DiagramPanel
              existingDiagram={existingDiagram}
              recommendedDiagram={recommendedDiagram}
              onSave={saveDiagram}
              savedAt={diagramSavedAt}
            />
          </div>
        )}
      </div>

      {/* KB-insufficient permission modal */}
      {kbPrompt && (
        <KbPermissionModal
          evt={kbPrompt}
          onSearchWeb={() => sendMessage({ allowWeb: true, resendQuery: kbPrompt.query })}
          onAnswerAnyway={() => sendMessage({ forceAnswer: true, resendQuery: kbPrompt.query })}
          onDismiss={() => setKbPrompt(null)}
        />
      )}
    </div>
  )
}

function KbPermissionModal({
  evt,
  onSearchWeb,
  onAnswerAnyway,
  onDismiss,
}: {
  evt: KbInsufficientEvent
  onSearchWeb: () => void
  onAnswerAnyway: () => void
  onDismiss: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4 bg-smoke/75 backdrop-blur-sm animate-fade-in-up">
      <div className="relative w-full max-w-lg rounded-2xl border border-ink-300 bg-white p-6">
        <button
          onClick={onDismiss}
          className="absolute top-3 right-3 p-1.5 rounded-md text-ink-500 hover:text-lc-black hover:bg-ink-100 transition"
          title="Dismiss"
        >
          <X size={14} />
        </button>

        <div className="flex items-center gap-2 text-lc-red mb-3">
          <BookOpenText size={16} />
          <span className="text-[11px] uppercase tracking-[0.18em] font-bold">Knowledge base coverage is thin</span>
        </div>

        <h2 className="font-display text-2xl text-lc-black leading-snug">
          Your KB returned {evt.kb_chunk_count} {evt.kb_chunk_count === 1 ? 'match' : 'matches'} for this
          question.
        </h2>
        <p className="mt-2 text-[14px] text-ink-600 text-pretty">
          Before searching the open web, confirm how you&apos;d like to proceed. Web results will be queued for
          your review before joining the KB.
        </p>

        {evt.kb_preview.length > 0 && (
          <div className="mt-4 rounded-lg border border-ink-300 bg-ink-50 p-3">
            <p className="text-[10px] uppercase tracking-[0.16em] text-ink-500 font-bold mb-2">Closest KB matches</p>
            <ul className="space-y-1">
              {evt.kb_preview.map((p, i) => (
                <li key={i} className="text-[12px] text-ink-800 flex items-center gap-2">
                  <span className="text-ink-500 tabular-nums">{(p.similarity ?? 0).toFixed(2)}</span>
                  <span className="truncate">{p.source_file || '—'}</span>
                  {p.jurisdiction && (
                    <span className="text-[10px] uppercase tracking-[0.14em] text-lc-red font-bold">
                      {p.jurisdiction}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <button
            onClick={onSearchWeb}
            className="lc-btn-primary py-3"
          >
            <Globe size={14} />
            Search the web
          </button>
          <button
            onClick={onAnswerAnyway}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-ink-50 border border-ink-300 text-ink-800 py-3 text-sm font-bold hover:bg-ink-100 hover:text-lc-black transition"
          >
            <BookOpenText size={14} />
            Answer from KB only
          </button>
        </div>

        <p className="mt-4 text-[11px] text-ink-500 leading-relaxed">
          <strong className="text-ink-800">Tip:</strong> if the topic should be covered by the KB, consider
          uploading supporting documents under <span className="text-lc-red">Knowledge base → Upload</span>.
        </p>
      </div>
    </div>
  )
}

function ThinkingDots() {
  return (
    <div className="inline-flex items-center gap-1 text-ink-500">
      <span className="h-1.5 w-1.5 bg-brass-400 rounded-full animate-bounce" />
      <span className="h-1.5 w-1.5 bg-brass-400 rounded-full animate-bounce" style={{ animationDelay: '0.12s' }} />
      <span className="h-1.5 w-1.5 bg-brass-400 rounded-full animate-bounce" style={{ animationDelay: '0.24s' }} />
    </div>
  )
}

function CenteredMessage({ text }: { text: string }) {
  return (
    <div className="py-20 text-center">
      <p className="text-ink-500 text-sm">{text}</p>
    </div>
  )
}

const SUGGESTIONS = [
  'Optimise UK-India succession with a discretionary trust structure',
  'Compare DIFC vs ADGM foundations for a UAE-resident founder',
  'Walk through Singapore VCC sub-fund taxation for a family office',
  'Taiwan inbound investment — CFC exposure and remedies',
]

function WelcomePrompt({ onSuggest }: { onSuggest: (s: string) => void }) {
  return (
    <div className="py-12 animate-fade-in-up">
      <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-brass-500/10 border border-brass-500/30 mb-5">
        <Sparkles size={22} className="text-brass-400" />
      </div>
      <h3 className="font-display text-2xl font-semibold text-ink-900 tracking-tight">How can I help?</h3>
      <p className="mt-2 text-sm text-ink-600">
        Ask anything about wealth planning across India, Singapore, UAE, USA, UK, Taiwan, China, or cross-border
        scenarios.
      </p>
      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-2">
        {SUGGESTIONS.map(s => (
          <button
            key={s}
            onClick={() => onSuggest(s)}
            className="text-left px-4 py-3 rounded-lg border border-ink-200 bg-white hover:bg-ink-50 hover:border-ink-300 transition text-[13px] text-ink-800"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}
