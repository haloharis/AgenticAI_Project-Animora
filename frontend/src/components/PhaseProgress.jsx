import { useState, useEffect } from 'react'

const PHASE_DEFS = [
  { id: 'story', name: 'Story & Script',    emoji: '📖', hint: '~12s' },
  { id: 'audio', name: 'Audio & Voices',    emoji: '🎙️', hint: '~24s' },
  { id: 'video', name: 'Video Composition', emoji: '🎬', hint: '~38s' },
]

const LOG_MESSAGES = {
  story: [
    'Drafting story structure…',
    'Generating character arcs…',
    'Writing scene 1: opening shot…',
    'Writing scene 2: rising action…',
    'Polishing dialogue…',
    'Finalizing script beats…',
  ],
  audio: [
    'Casting character voices…',
    'Converting dialogue to speech…',
    'Generating ambient soundscape…',
    'Composing background score…',
    'Mixing voice and music tracks…',
    'Mastering audio output…',
  ],
  video: [
    'Generating keyframes…',
    'Rendering scene 1 visuals…',
    'Compositing scene transitions…',
    'Synchronising audio to video…',
    'Applying colour grading…',
    'Encoding final MP4…',
  ],
}

function PhaseLog({ phaseId }) {
  const [idx, setIdx] = useState(0)
  const messages = LOG_MESSAGES[phaseId] || []

  useEffect(() => {
    const i = setInterval(() => setIdx(n => (n + 1) % messages.length), 1800)
    return () => clearInterval(i)
  }, [phaseId, messages.length])

  const current = messages[idx]
  const prev    = messages[(idx - 1 + messages.length) % messages.length]

  return (
    <div className="phase-log">
      <div className="phase-log-line" key={`p-${idx}`} style={{ animationDelay: '-1.5s' }}>
        <span className="glyph">›</span>{prev}
      </div>
      <div className="phase-log-line fresh" key={`c-${idx}`}>
        <span className="glyph">›</span>{current}
      </div>
    </div>
  )
}

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

export default function PhaseProgress({ phases, onRerun }) {
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

              {ph.status === 'running' && <PhaseLog phaseId={p.id} />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
