export function createSSEStream(
  url: string,
  token: string,
  body: object,
  onToken: (text: string) => void,
  onSources: (sources: any) => void,
  onDone: () => void,
  onDiagram?: (diagram: { nodes: any[]; edges: any[] }) => void,
) {
  const controller = new AbortController()

  let doneCalled = false
  const callDone = () => {
    if (!doneCalled) { doneCalled = true; onDone() }
  }

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).then(async (res) => {
    if (!res.ok || !res.body) {
      console.error('SSE request failed:', res.status)
      callDone()
      return
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'token') onToken(data.text)
              else if (data.type === 'sources') onSources(data)
              else if (data.type === 'diagram_update' && onDiagram) onDiagram(data.diagram)
              else if (data.type === 'done') callDone()
            } catch {
              // ignore malformed SSE line
            }
          }
        }
      }
    } finally {
      callDone()  // ensure done is always called
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') console.error('SSE error:', err)
    callDone()  // always reset streaming state
  })

  return () => controller.abort()
}
