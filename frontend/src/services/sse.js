export function connectSSE(jobId, onEvent, onError) {
  const es = new EventSource(`/api/events/${jobId}`)
  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      onEvent(data)
      if (data.type === 'done') {
        es.close()
      }
    } catch (err) {
      console.warn('SSE parse error:', err)
    }
  }
  es.onerror = (e) => {
    if (onError) onError(e)
    es.close()
  }
  return es
}
