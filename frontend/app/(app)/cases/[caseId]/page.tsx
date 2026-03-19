'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { DiagramPanel } from '@/components/diagram/DiagramPanel'
import { createSSEStream } from '@/lib/sse-client'

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
  const token = (session as any)?.accessToken as string ?? ''

  const [caseData, setCaseData] = useState<CaseData | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
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

    fetch(`${apiUrl}/cases/${caseId}/history`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : [])
      .then((history: any[]) => {
        const msgs: Message[] = history.map((h: any) => ({
          id: crypto.randomUUID(),
          role: h.role,
          content: h.content,
          sources: h.sources,
        }))
        setMessages(msgs)
      })
      .catch(() => {})
  }, [caseId, token, apiUrl])

  const sendMessage = useCallback(() => {
    if (!input.trim() || streaming || !token) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', content: userMsg }])
    setStreaming(true)

    let assistantContent = ''
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: '' }])

    const abort = createSSEStream(
      `${apiUrl}/cases/${caseId}/chat`,
      token,
      { message: userMsg },
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
            {/* Messages */}
            <div className="flex-1 overflow-y-auto space-y-4 mb-4">
              {messages.length === 0 && (
                <div className="flex items-center justify-center h-full">
                  <p className="text-slate-400 text-sm">Start a conversation about this case.</p>
                </div>
              )}
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white border border-slate-200 text-slate-800'
                  }`}>
                    {msg.content || (msg.role === 'assistant' && streaming && msg.id === messages[messages.length - 1]?.id ? (
                      <span className="inline-flex gap-1">
                        <span className="animate-bounce delay-0">.</span>
                        <span className="animate-bounce delay-100">.</span>
                        <span className="animate-bounce delay-200">.</span>
                      </span>
                    ) : '')}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-100">
                        <p className="text-xs text-slate-400 mb-1">Sources:</p>
                        <div className="flex flex-wrap gap-1">
                          {msg.sources.slice(0, 4).map((s: any, si: number) => (
                            <span key={si} className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                              {s.title || s.source || `Source ${si + 1}`}
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
