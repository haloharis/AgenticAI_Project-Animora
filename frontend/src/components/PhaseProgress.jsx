const PHASE_DEFS = [
  { id: 'story', name: 'Story & Script',    emoji: '📖', hint: '~12s' },
  { id: 'audio', name: 'Audio & Voices',    emoji: '🎙️', hint: '~24s' },
  { id: 'video', name: 'Video Composition', emoji: '🎬', hint: '~38s' },
]

function StatusBadge({ status }) {
  if (!status || status === 'pending') {
    return <span className="status-badge"><span className="pip" />Queued</span>
  }
  if (status === 'running') {
    return <span className="status-badge running"><span className="pip" />Running</span>
  }
  if (status === 'completed') {
    return <span className="status-badge completed"><span className="pip" />Done</span>
  }
  if (status === 'failed') {
    return <span className="status-badge failed"><span className="pip" />Failed</span>
  }
  return null
}

export default function PhaseProgress({ phases, onRerun, logs = [] }) {
  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          <span className="icon">⚙</span>
          Pipeline
        </h3>
        <span className="card-subtitle" style={{ margin: 0, fontSize: 12 }}>
          3 phases · live updates
        </span>
      </div>

      <div className="phases">
        {PHASE_DEFS.map(p => {
          const ph  = phases[p.id] || { status: 'pending', progress: 0 }
          const cls = `phase is-${ph.status || 'pending'}`
          return (
            <div className={cls} data-phase={p.id} key={p.id}>
              <div className="phase-row">
                <div className="phase-icon">{p.emoji}</div>
                <div className="phase-meta">
                  <div className="phase-title-row">
                    <span className="phase-name">{p.name}</span>
                    <span className="phase-hint">{p.hint}</span>
                  </div>
                  <div className="phase-status-row">
                    <StatusBadge status={ph.status} />
                    {ph.status === 'failed' && ph.error && (
                      <span style={{ color: 'var(--error)', fontSize: 12 }}>{ph.error}</span>
                    )}
                    <span className="progress-pct">{Math.round(ph.progress || 0)}%</span>
                  </div>
                </div>
                {(ph.status === 'completed' || ph.status === 'failed') && (
                  <button
                    type="button"
                    className="phase-action"
                    onClick={() => onRerun && onRerun(p.id)}
                    title={ph.status === 'failed' ? 'Retry' : 'Re-run this phase'}
                    style={ph.status === 'failed' ? { color: 'var(--error)' } : {}}
                  >↻</button>
                )}
              </div>

              <div className="progress-bar">
                <div
                  className="progress-bar-fill"
                  style={{ width: `${ph.progress || 0}%` }}
                />
              </div>

              {ph.status === 'running' && (() => {
                const latest = [...logs].reverse().find(l => l.phase === p.id)
                return latest ? (
                  <div className="phase-log-live" key={latest.ts}>
                    <span className="glyph">›</span>{latest.message}
                  </div>
                ) : (
                  <div className="phase-log-live">
                    <span className="glyph">›</span>Processing…
                  </div>
                )
              })()}
            </div>
          )
        })}
      </div>
    </div>
  )
}
