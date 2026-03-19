'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { DiagramPanel } from '@/components/diagram/DiagramPanel'
import { createSSEStream } from '@/lib/sse-client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

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
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<(() => void) | null>(null)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    return () => {
      // Cleanup: abort any active SSE stream when component unmounts
      if (abortRef.current) {
        abortRef.current()
      }
    }
  }, [])

  useEffect(() => {
    if (!token) return
    fetch(`${apiUrl}/cases/${caseId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setCaseData(data) })
      .catch(() => {})

    Promise.all([
      fetch(`${apiUrl}/cases/${caseId}/history`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => r.ok ? r.json() : []),
      fetch(`${apiUrl}/cases/${caseId}/summary`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => r.ok ? r.json() : { summary: '' }),
    ]).then(([history, summaryData]) => {
      const msgs: Message[] = history.map((h: any) => ({
        id: crypto.randomUUID(),
        role: h.role,
        content: h.content,
        sources: h.sources,
      }))
      setMessages(msgs)
      if (summaryData.summary) setHasPriorMemory(true)
    }).catch(() => {}).finally(() => setHistoryLoading(false))
  }, [caseId, token, apiUrl])

  const sendMessage = useCallback(() => {
    if (!input.trim() || streaming || !token) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', content: userMsg }])
    setStreaming(true)
    setChatError(null)

    let assistantContent = ''
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: '' }])

    const abort = createSSEStream(
      `${apiUrl}/chat/stream`,
      token,
      { message: userMsg, case_id: caseId },
      (text) => {
        assistantContent += text
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { ...updated[updated.length - 1], content: assistantContent }
          return updated
        })
      },
      (sourcesData) => {
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
      },
      () => {
        setStreaming(false)
        abortRef.current = null
      },
      (diagramData) => {
        setRecommendedDiagram(diagramData)
      },
      (errMsg) => {
        setChatError(errMsg)
        setStreaming(false)
      },
    )

    abortRef.current = abort
  }, [input, streaming, token, caseId, apiUrl])

  async function downloadPdf() {
    const res = await fetch(`${apiUrl}/reports/${caseId}/pdf`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) return
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `wealth-plan-${caseId.slice(0, 8)}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">
            {caseData?.client_name || 'Loading...'}
          </h1>
          <p className="text-slate-500 text-xs mt-0.5">Case ID: {caseId.slice(0, 8)}...</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg border border-slate-200 overflow-hidden">
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-4 py-1.5 text-sm font-medium transition ${activeTab === 'chat' ? 'bg-blue-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
            >
              Chat
            </button>
            <button
              onClick={() => setActiveTab('diagram')}
              className={`px-4 py-1.5 text-sm font-medium transition ${activeTab === 'diagram' ? 'bg-blue-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
            >
              Structure
            </button>
          </div>
          <button
            onClick={downloadPdf}
            className="px-4 py-1.5 text-sm font-medium bg-slate-800 text-white rounded-lg hover:bg-slate-700 transition"
          >
            Download PDF
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'chat' ? (
          <div className="flex flex-col h-full">
            {/* Memory banner */}
            {hasPriorMemory && (
              <div className="mb-3 flex items-center gap-2 bg-blue-50 border border-blue-100 rounded-lg px-4 py-2 text-xs text-blue-700">
                <span>🧠</span>
                <span><strong>Session memory active</strong> — the AI has context from your previous conversations on this case.</span>
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto space-y-4 mb-4">
              {historyLoading ? (
                <div className="flex items-center justify-center h-full">
                  <p className="text-slate-400 text-sm">Loading conversation history...</p>
                </div>
              ) : messages.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <p className="text-slate-400 text-sm">Start a conversation about this case.</p>
                </div>
              ) : null}
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`rounded-xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'max-w-[65%] bg-blue-600 text-white'
                      : 'w-full bg-white border border-slate-200 text-slate-800'
                  }`}>
                    {msg.role === 'user' ? (
                      <p>{msg.content}</p>
                    ) : msg.content ? (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h3: ({children}) => <h3 className="text-base font-bold text-slate-900 mt-4 mb-2 first:mt-0">{children}</h3>,
                          h4: ({children}) => <h4 className="text-sm font-semibold text-slate-800 mt-3 mb-1">{children}</h4>,
                          ul: ({children}) => <ul className="list-disc list-outside ml-4 space-y-1 my-2">{children}</ul>,
                          ol: ({children}) => <ol className="list-decimal list-outside ml-4 space-y-1 my-2">{children}</ol>,
                          li: ({children}) => <li className="text-slate-700 leading-relaxed">{children}</li>,
                          p: ({children}) => <p className="text-slate-700 mb-2 last:mb-0">{children}</p>,
                          strong: ({children}) => <strong className="font-semibold text-slate-900">{children}</strong>,
                          hr: () => <hr className="my-3 border-slate-200" />,
                          blockquote: ({children}) => <blockquote className="border-l-4 border-blue-200 pl-3 text-slate-600 italic my-2">{children}</blockquote>,
                          code: ({children}) => <code className="bg-slate-100 text-slate-700 px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    ) : streaming && msg.id === messages[messages.length - 1]?.id ? (
                      <span className="inline-flex gap-1 text-slate-400">
                        <span className="animate-bounce">.</span>
                        <span className="animate-bounce" style={{animationDelay:'0.1s'}}>.</span>
                        <span className="animate-bounce" style={{animationDelay:'0.2s'}}>.</span>
                      </span>
                    ) : null}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-100">
                        <p className="text-xs font-medium text-slate-400 mb-1.5">Sources used:</p>
                        <div className="flex flex-wrap gap-1">
                          {msg.sources.slice(0, 5).map((s: any, si: number) => (
                            <span key={si} className="text-xs bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-full">
                              {s.source_file || s.title || `Source ${si + 1}`}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>


            {/* Error */}
            {chatError && (
              <div className="mb-2 bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-700">
                ⚠️ {chatError}
              </div>
            )}

            {/* Input */}
            <div className="flex gap-2 items-end">
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about tax optimisation, succession planning, structures..."
                rows={2}
                disabled={streaming}
                className="flex-1 border border-slate-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none disabled:opacity-50"
              />
              <button
                onClick={sendMessage}
                disabled={streaming || !input.trim()}
                className="px-5 py-3 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition disabled:opacity-50 whitespace-nowrap"
              >
                {streaming ? 'Thinking...' : 'Send'}
              </button>
            </div>
          </div>
        ) : (
          <div className="h-full">
            <DiagramPanel existingDiagram={existingDiagram} recommendedDiagram={recommendedDiagram} />
          </div>
        )}
      </div>
    </div>
  )
}
