import { useState, useRef, useCallback } from 'react'
import PromptInput from './components/PromptInput'
import PhaseProgress from './components/PhaseProgress'
import VideoPreview from './components/VideoPreview'
import EditAgent from './components/EditAgent'
import { startPipeline, submitEdit, getHistory, revertVersion, rerunPhase, getVideoUrl } from './services/api'
import { connectSSE } from './services/sse'

const INITIAL_PHASES = {
  story: { status: 'pending', progress: 0 },
  audio: { status: 'pending', progress: 0 },
  video: { status: 'pending', progress: 0 },
}

const PHASE_MAP = {
  script:      ['story', 'audio', 'video'],
  audio:       ['audio', 'video'],
  video_frame: ['video'],
  video:       ['video'],
}

function mapHistory(items) {
  return (items || []).map(h => ({
    version:    h.version,
    phase:      h.phase || 'story',
    note:       h.note || h.message || '',
    created_at: h.created_at ? new Date(h.created_at).getTime() : Date.now(),
  }))
}

export default function App() {
  const [jobId,          setJobId]          = useState(null)
  const [phases,         setPhases]         = useState(INITIAL_PHASES)
  const [videoUrl,       setVideoUrl]       = useState(null)
  const [isGenerating,   setIsGenerating]   = useState(false)
  const [error,          setError]          = useState(null)
  const [prompt,         setPrompt]         = useState('')
  const [style,          setStyle]          = useState('cinematic')
  const [versions,       setVersions]       = useState([])
  const [currentVersion, setCurrentVersion] = useState(1)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const sseRef = useRef(null)

  const applySSEEvent = useCallback((evt, job_id) => {
    if (evt.phase) {
      setPhases(p => ({
        ...p,
        [evt.phase]: { status: evt.status, progress: evt.progress || 0, error: evt.error || null },
      }))
    }
    if (evt.type === 'done') {
      setIsGenerating(false)
      if (evt.success) {
        setVideoUrl(getVideoUrl(job_id))
        setLoadingHistory(true)
        getHistory(job_id)
          .then(h => {
            const mapped = mapHistory(h)
            setVersions(mapped)
            if (mapped.length > 0) setCurrentVersion(mapped[mapped.length - 1].version)
          })
          .catch(() => {})
          .finally(() => setLoadingHistory(false))
      } else {
        setError(evt.error || 'Pipeline failed. Please try again.')
      }
    }
  }, [])

  const handleSubmit = useCallback(async () => {
    if (!prompt.trim() || isGenerating) return
    setError(null)
    setIsGenerating(true)
    setVideoUrl(null)
    setPhases(INITIAL_PHASES)
    setVersions([])
    setCurrentVersion(1)
    setLoadingHistory(false)
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null }

    try {
      const { job_id } = await startPipeline(prompt, style)
      setJobId(job_id)
      sseRef.current = connectSSE(job_id, evt => applySSEEvent(evt, job_id), () => {})
    } catch (e) {
      setIsGenerating(false)
      setError(`Failed to start: ${e.message}`)
    }
  }, [prompt, style, isGenerating, applySSEEvent])

  const handleRerun = useCallback(async (phase) => {
    if (!jobId) return
    const order = ['story', 'audio', 'video']
    const fromIdx = order.indexOf(phase)
    setPhases(p => {
      const next = { ...p }
      order.slice(fromIdx).forEach((ph, i) => {
        next[ph] = { status: i === 0 ? 'running' : 'pending', progress: 0 }
      })
      return next
    })
    setIsGenerating(true)
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null }
    sseRef.current = connectSSE(jobId, evt => applySSEEvent(evt, jobId), () => {})
    try {
      await rerunPhase(jobId, phase)
    } catch (e) {
      setIsGenerating(false)
      setPhases(p => ({ ...p, [phase]: { status: 'failed', progress: 0, error: e.message } }))
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null }
      setError(e.message)
    }
  }, [jobId, applySSEEvent])

  const handleApplyEdit = useCallback(async (query) => {
    try {
      const result = await submitEdit(jobId, query)
      if (!result.success) {
        return {
          success:       false,
          clarification: result.clarification || "I couldn't determine what to change. Please be more specific.",
        }
      }
      const intent      = result.action?.intent || 'video'
      const phasesRerun = PHASE_MAP[intent] || ['video']

      setPhases(p => {
        const next = { ...p }
        phasesRerun.forEach(ph => { next[ph] = { status: 'completed', progress: 100 } })
        return next
      })
      setVideoUrl(getVideoUrl(jobId) + '?t=' + Date.now())

      const h      = await getHistory(jobId)
      const mapped = mapHistory(h)
      setVersions(mapped)
      const newVer = result.new_version || (mapped.length > 0 ? mapped[mapped.length - 1].version : currentVersion + 1)
      setCurrentVersion(newVer)

      return {
        success:      true,
        intent,
        phases_rerun: phasesRerun,
        new_version:  newVer,
        message:      result.message || `Re-ran ${phasesRerun.join(' + ')} to apply your change.`,
      }
    } catch (e) {
      return { success: false, clarification: `Edit failed: ${e.message}` }
    }
  }, [jobId, currentVersion])

  const handleRevert = useCallback(async (version) => {
    try {
      const result = await revertVersion(jobId, version)
      setCurrentVersion(version)
      if (result.has_video) setVideoUrl(getVideoUrl(jobId) + '?t=' + Date.now())
      if (result.phases) {
        setPhases(p => {
          const next = { ...p }
          Object.entries(result.phases).forEach(([k, v]) => {
            next[k] = { status: v.status, progress: v.progress_pct || 0, error: v.error || null }
          })
          return next
        })
      }
      const h = await getHistory(jobId)
      setVersions(mapHistory(h))
    } catch (e) {
      setError(`Revert failed: ${e.message}`)
    }
  }, [jobId])

  const activeMini = phases.story.status === 'running' ? 'story'
    : phases.audio.status === 'running' ? 'audio'
    : phases.video.status === 'running' ? 'video'
    : null

  const overlayMessages = {
    story: 'Drafting story structure…',
    audio: 'Casting voices and composing audio…',
    video: 'Rendering scenes and encoding video…',
  }

  return (
    <>
      <div className="bg-atmosphere">
        <div className="bg-nebula n1" />
        <div className="bg-nebula n2" />
        <div className="bg-nebula n3" />
        <div className="bg-stars" />
        <div className="bg-stars2" />
        <div className="bg-stars3" />
      </div>

      <main className="app">
        <header className="hero">
          <div className="hero-eyebrow">
            <span className="dot" />
            <span>Pipeline online · 3-phase render</span>
          </div>
          <h1>Animora<span className="blink" /></h1>
          <p className="tagline">
            Prompt <span className="arrow">→</span> Animated Short Film
          </p>
        </header>

        {error && (
          <div className="error-banner">
            <div className="icon">!</div>
            <div className="msg">{error}</div>
            <button className="retry" onClick={handleSubmit}>Retry</button>
            <button className="dismiss" onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        <div className="grid">
          <div className="col">
            <PromptInput
              prompt={prompt}
              setPrompt={setPrompt}
              style={style}
              setStyle={setStyle}
              onSubmit={handleSubmit}
              isGenerating={isGenerating}
            />
            <PhaseProgress phases={phases} onRerun={handleRerun} />
          </div>

          <div className="col">
            <VideoPreview videoUrl={videoUrl} jobId={jobId} />
            {jobId && (
              <EditAgent
                jobId={jobId}
                isGenerating={isGenerating}
                versions={versions}
                currentVersion={currentVersion}
                onApplyEdit={handleApplyEdit}
                onRevert={handleRevert}
                loadingHistory={loadingHistory}
              />
            )}
          </div>
        </div>

        <footer className="foot">
          ANIMORA <span className="sep">·</span> AI VIDEO PIPELINE <span className="sep">·</span> 3-PHASE RENDER
        </footer>
      </main>

      {isGenerating && !videoUrl && (
        <div className="gen-overlay">
          <div className="gen-overlay-inner">
            <div className="gen-logo">
              <span className="gen-logo-glyph">A</span>
            </div>
            <h2>Generating your story…</h2>
            <p className="sub" key={activeMini}>
              {activeMini ? overlayMessages[activeMini] : 'Spinning up the pipeline…'}
            </p>
            <div className="mini-phases">
              {['story', 'audio', 'video'].map(p => {
                const ph  = phases[p]
                const cls = ph.status === 'completed'
                  ? 'mini-phase done'
                  : ph.status === 'running'
                    ? 'mini-phase active'
                    : 'mini-phase'
                return (
                  <div key={p} className={cls}>
                    <span className="pip" />
                    <span style={{ textTransform: 'capitalize' }}>{p}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
