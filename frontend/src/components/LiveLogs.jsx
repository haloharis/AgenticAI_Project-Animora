import { useEffect, useRef } from 'react'

export default function LiveLogs({ logs = [], isGenerating }) {
  const bodyRef = useRef(null)

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [logs])

  if (!isGenerating && logs.length === 0) return null

  return (
    <div className="live-logs">
      <div className="live-logs-header">
        {isGenerating && <span className="live-logs-dot" />}
        <span>Pipeline Logs</span>
        <span style={{ marginLeft: 'auto', opacity: 0.5 }}>{logs.length} lines</span>
      </div>
      <div className="live-logs-body" ref={bodyRef}>
        {logs.length === 0 ? (
          <span className="live-logs-empty">Waiting for logs…</span>
        ) : (
          logs.map((entry, i) => (
            <div key={i} className={`log-line${entry.level !== 'info' ? ` ${entry.level}` : ''}`}>
              {entry.phase && <span className="log-phase-tag">[{entry.phase}]</span>}
              <span className="log-msg">{entry.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
