import { useState, useEffect } from 'react'

const INTENT_DEFS = {
  audio: {
    label: 'Audio',
    emoji: '🎙️',
    color: '#4a9eff',
    chips: ['Make it sadder', 'Add dramatic music', 'Louder voices'],
  },
  video_frame: {
    label: 'Visual',
    emoji: '🖼️',
    color: '#c084fc',
    chips: ['Change to night scene', 'Make it darker', 'More vibrant colors'],
  },
  video: {
    label: 'Video',
    emoji: '🎬',
    color: '#4ade80',
    chips: ['Add subtitles', 'Faster pace', 'Smoother transitions'],
  },
  script: {
    label: 'Script',
    emoji: '📝',
    color: '#a78bfa',
    chips: ['Rewrite the ending', 'Add more dialogue', 'Make it funnier'],
  },
}

const PHASE_COLOR = {
  story:       '#a78bfa',
  audio:       '#4a9eff',
  video:       '#4ade80',
  video_frame: '#c084fc',
}

function timeAgo(date) {
  const s = Math.floor((Date.now() - date) / 1000)
  if (s < 5)  return 'just now'
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  return `${Math.floor(m / 60)}h ago`
}

export default function EditAgent({
  jobId,
  isGenerating,
  versions,
  currentVersion,
  onApplyEdit,
  onRevert,
  loadingHistory,
}) {
  const [query,       setQuery]       = useState('')
  const [reply,       setReply]       = useState(null)
  const [submitting,  setSubmitting]  = useState(false)
  const [stage,       setStage]       = useState('')
  const [historyOpen, setHistoryOpen] = useState(true)

  useEffect(() => {
    if (reply?.type === 'success') {
      const t = setTimeout(() => setReply(null), 4500)
      return () => clearTimeout(t)
    }
  }, [reply])

  const submit = async () => {
    if (!query.trim() || submitting || isGenerating) return
    setSubmitting(true)
    setStage('analyzing')
    setReply({ type: 'thinking', text: 'Analyzing your request…' })
    await new Promise(r => setTimeout(r, 700))
    setStage('applying')
    const result = await onApplyEdit(query.trim())
    setSubmitting(false)
    setStage('')
    if (result.success) {
      setReply({
        type:    'success',
        intent:  result.intent,
        rerun:   result.phases_rerun,
        version: result.new_version,
        message: result.message,
      })
      setQuery('')
    } else {
      setReply({ type: 'warning', clarification: result.clarification })
    }
  }

  return (
    <div className="card edit-agent">
      <div className="card-header">
        <h3 className="card-title">
          <span className="icon">✏️</span>
          Edit with AI
        </h3>
        <span className="card-subtitle" style={{ margin: 0, fontSize: 12 }}>
          v{currentVersion || 1}
        </span>
      </div>
      <p className="card-subtitle">
        Describe changes in plain language — the AI figures out which phases to re-run.
      </p>

      <div className="chip-rows">
        {Object.entries(INTENT_DEFS).map(([id, def]) => (
          <div className="chip-row" key={id}>
            <span className="chip-row-label" style={{ '--swatch': def.color }}>
              <span className="swatch" />
              {def.emoji} {def.label}
            </span>
            {def.chips.map(c => (
              <button
                key={c}
                type="button"
                className="chip"
                style={{ '--swatch': def.color }}
                onClick={() => setQuery(c)}
                disabled={isGenerating}
              >{c}</button>
            ))}
          </div>
        ))}
      </div>

      <div className="edit-input-wrap">
        <div className="edit-textarea-wrap">
          <textarea
            className="edit-textarea"
            placeholder={
              isGenerating
                ? 'Editing available once generation finishes…'
                : 'Describe the change you want — e.g. "Make scene 2 take place at sunset with a melancholic piano score"'
            }
            value={query}
            onChange={e => setQuery(e.target.value)}
            disabled={isGenerating || submitting}
            onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit() }}
          />
        </div>
        <button
          type="button"
          className={`edit-apply ${submitting ? 'is-loading' : ''}`}
          onClick={submit}
          disabled={isGenerating || submitting || !query.trim()}
        >
          {submitting ? (
            <><span className="spinner" />{stage === 'analyzing' ? 'Analyzing…' : 'Applying…'}</>
          ) : (
            <>Apply Edit →</>
          )}
        </button>
      </div>

      {reply?.type === 'thinking' && (
        <div className="agent-reply">
          <div className="agent-avatar"><span className="spinner" /></div>
          <div className="agent-content">
            <div className="agent-line">{reply.text}</div>
            <div className="agent-line muted">Classifying intent and planning phases to re-run…</div>
          </div>
        </div>
      )}

      {reply?.type === 'success' && (
        <div className="agent-reply success">
          <div className="agent-avatar">✓</div>
          <div className="agent-content">
            <div className="agent-line">
              <strong>Got it.</strong> Saved as <strong>v{reply.version}</strong>.
              {reply.message ? ` ${reply.message}` : ''}
            </div>
            <div className="agent-meta">
              {reply.intent && (
                <span
                  className="intent-chip"
                  style={{ '--intent-color': INTENT_DEFS[reply.intent]?.color }}
                >
                  {INTENT_DEFS[reply.intent]?.emoji} Detected: {INTENT_DEFS[reply.intent]?.label} edit
                </span>
              )}
              {(reply.rerun || []).map(ph => (
                <span className="rerun-tag" key={ph}>
                  <span className="ph-dot" style={{ '--ph': PHASE_COLOR[ph] || '#888' }} />
                  re-ran {ph}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {reply?.type === 'warning' && (
        <div className="agent-reply warning">
          <div className="agent-avatar" style={{ background: 'linear-gradient(135deg, #fbbf24, #f59e0b)' }}>⚠</div>
          <div className="agent-content">
            <div className="agent-line"><strong>I need a bit more detail.</strong></div>
            <div className="agent-line muted">{reply.clarification}</div>
          </div>
        </div>
      )}

      <button
        type="button"
        className={`history-toggle ${historyOpen ? 'open' : ''}`}
        onClick={() => setHistoryOpen(o => !o)}
      >
        <span>
          📜 Edit History
          {versions?.length > 0 && ` · ${versions.length} version${versions.length === 1 ? '' : 's'}`}
        </span>
        <span className="chev">⌄</span>
      </button>

      {historyOpen && (
        loadingHistory ? (
          <div className="timeline" style={{ paddingLeft: 24 }}>
            <div className="skeleton" />
            <div className="skeleton" style={{ width: '85%' }} />
            <div className="skeleton" style={{ width: '70%' }} />
          </div>
        ) : (
          <div className="timeline">
            {(versions || []).map(v => {
              const phaseColor = PHASE_COLOR[v.phase] || 'var(--accent)'
              const isCurrent  = v.version === currentVersion
              return (
                <div
                  key={v.version}
                  className={`timeline-item ${isCurrent ? 'current' : ''}`}
                  style={{ '--dot-color': phaseColor }}
                >
                  <span className="timeline-dot" />
                  <span className="tl-version">v{v.version}</span>
                  <span className="tl-phase" style={{ color: phaseColor }}>{v.phase}</span>
                  <span className="tl-note">{v.note}</span>
                  <span className="tl-time">{timeAgo(v.created_at)}</span>
                  {isCurrent ? (
                    <span className="tl-current-tag">current</span>
                  ) : (
                    <button
                      type="button"
                      className="tl-revert"
                      onClick={() => onRevert && onRevert(v.version)}
                    >↩ Revert</button>
                  )}
                </div>
              )
            })}
            {(!versions || versions.length === 0) && (
              <div style={{ color: 'var(--muted)', fontSize: 13, paddingLeft: 0, marginLeft: -24 }}>
                No edits yet. Try one of the suggestions above to remix your video.
              </div>
            )}
          </div>
        )
      )}
    </div>
  )
}
