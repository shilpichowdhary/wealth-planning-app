export function createSSEStream(
  url: string,
  token: string,
  body: object,
  onToken: (text: string) => void,
  onSources: (sources: any) => void,
  onDone: () => void,
) {
  const controller = new AbortController()

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).then(async (res) => {
    if (!res.ok || !res.body) {
      console.error('SSE request failed:', res.status)
      onDone()
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
              else if (data.type === 'done') onDone()
            } catch {
              // ignore malformed SSE line
            }
          }
        }
      }
    } finally {
      onDone()  // ensure done is always called
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') console.error('SSE error:', err)
    onDone()  // always reset streaming state
  })

  return () => controller.abort()
}
