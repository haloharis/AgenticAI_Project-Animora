const { useState, useEffect, useRef, useCallback } = React;

// ----------------------------------------------------------------
// Demo backend simulation
// In production this would be replaced with the real fetch + EventSource calls.
// ----------------------------------------------------------------
const DEMO = true;

function makeJobId() {
  return 'job_' + Math.random().toString(36).slice(2, 10);
}

function simulatePipeline(onEvent, opts = {}) {
  const { onlyPhases = ['story', 'audio', 'video'] } = opts;
  let cancelled = false;
  const timers = [];
  const phaseDurations = { story: 2400, audio: 3000, video: 3800 };

  let delay = 0;
  onlyPhases.forEach((phase) => {
    const dur = phaseDurations[phase];
    const steps = 20;
    timers.push(setTimeout(() => {
      if (cancelled) return;
      onEvent({ phase, status: 'running', progress: 0 });
      for (let i = 1; i <= steps; i++) {
        timers.push(setTimeout(() => {
          if (cancelled) return;
          const progress = Math.min(100, Math.round((i / steps) * 100));
          onEvent({ phase, status: i === steps ? 'completed' : 'running', progress });
        }, (dur / steps) * i));
      }
    }, delay));
    delay += dur + 200;
  });

  timers.push(setTimeout(() => {
    if (!cancelled) onEvent({ type: 'done', success: true });
  }, delay + 100));

  return () => {
    cancelled = true;
    timers.forEach(clearTimeout);
  };
}

function App() {
  // Tweaks
  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
    "showDemoBanner": true,
    "autoSeedDemo": true,
    "accent": "#6c63ff"
  }/*EDITMODE-END*/;
  const [tweaks, setTweak] = window.useTweaks
    ? window.useTweaks(TWEAK_DEFAULTS)
    : [TWEAK_DEFAULTS, () => {}];

  // App state — exact same shape the spec requires
  const [jobId, setJobId] = useState(null);
  const [phases, setPhases] = useState({
    story: { status: 'pending', progress: 0 },
    audio: { status: 'pending', progress: 0 },
    video: { status: 'pending', progress: 0 },
  });
  const [videoUrl, setVideoUrl] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);

  // UI inputs
  const [prompt, setPrompt] = useState('');
  const [style, setStyle] = useState('cinematic');

  // Edit / version state
  const [versions, setVersions] = useState([]);
  const [currentVersion, setCurrentVersion] = useState(1);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const cancelRef = useRef(null);

  const handleSubmit = useCallback(() => {
    if (!prompt.trim()) return;
    setError(null);
    const id = makeJobId();
    setJobId(id);
    setVideoUrl(null);
    setIsGenerating(true);
    setPhases({
      story: { status: 'pending', progress: 0 },
      audio: { status: 'pending', progress: 0 },
      video: { status: 'pending', progress: 0 },
    });
    setVersions([]);
    setCurrentVersion(1);
    setLoadingHistory(true);

    setTimeout(() => {
      setVersions([{
        version: 1,
        phase: 'story',
        note: prompt.length > 60 ? prompt.slice(0, 60) + '…' : prompt,
        created_at: Date.now(),
      }]);
      setLoadingHistory(false);
    }, 600);

    if (cancelRef.current) cancelRef.current();
    cancelRef.current = simulatePipeline((evt) => {
      if (evt.type === 'done') {
        setIsGenerating(false);
        if (evt.success) {
          // Sample MP4 (small public domain clip)
          setVideoUrl('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4');
        } else {
          setError('Pipeline failed. Please try again.');
        }
        return;
      }
      setPhases((p) => ({ ...p, [evt.phase]: { status: evt.status, progress: evt.progress } }));
    });
  }, [prompt]);

  const handleRerun = useCallback((phase) => {
    setPhases((p) => {
      const next = { ...p };
      next[phase] = { status: 'running', progress: 0 };
      // downstream phases also need to re-run
      const order = ['story', 'audio', 'video'];
      const fromIdx = order.indexOf(phase);
      order.slice(fromIdx + 1).forEach((p2) => {
        next[p2] = { status: 'pending', progress: 0 };
      });
      return next;
    });
    setIsGenerating(true);
    if (cancelRef.current) cancelRef.current();
    const order = ['story', 'audio', 'video'];
    const fromIdx = order.indexOf(phase);
    cancelRef.current = simulatePipeline((evt) => {
      if (evt.type === 'done') {
        setIsGenerating(false);
        return;
      }
      setPhases((p) => ({ ...p, [evt.phase]: { status: evt.status, progress: evt.progress } }));
    }, { onlyPhases: order.slice(fromIdx) });
  }, []);

  const handleApplyEdit = useCallback(async (query) => {
    const intent = window.classifyIntent(query);
    if (!intent) {
      return {
        success: false,
        clarification:
          "I couldn't tell what you'd like to change. Try mentioning the audio (music, voices), the visuals (scene, colors, lighting), the script (dialogue, ending), or the video (pace, subtitles).",
      };
    }
    // Map intent → phases to re-run
    const phaseMap = {
      script: ['story', 'audio', 'video'],
      audio: ['audio', 'video'],
      video_frame: ['video'],
      video: ['video'],
    };
    const phasesToRerun = phaseMap[intent];

    // Animate phases back to running
    setPhases((p) => {
      const next = { ...p };
      phasesToRerun.forEach((ph) => { next[ph] = { status: 'running', progress: 0 }; });
      return next;
    });
    setIsGenerating(true);
    if (cancelRef.current) cancelRef.current();
    cancelRef.current = simulatePipeline((evt) => {
      if (evt.type === 'done') {
        setIsGenerating(false);
        // Rotate to a different sample video to make the change feel real
        const samples = [
          'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
          'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4',
          'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4',
        ];
        setVideoUrl(samples[Math.floor(Math.random() * samples.length)]);
        return;
      }
      setPhases((p) => ({ ...p, [evt.phase]: { status: evt.status, progress: evt.progress } }));
    }, { onlyPhases: phasesToRerun });

    const newVersion = (versions[versions.length - 1]?.version || currentVersion) + 1;
    const phaseLabel = intent === 'video_frame' ? 'video_frame' : (phasesToRerun[0]);
    setVersions((vs) => [
      ...vs,
      {
        version: newVersion,
        phase: phaseLabel,
        note: query,
        created_at: Date.now(),
      },
    ]);
    setCurrentVersion(newVersion);

    return {
      success: true,
      new_version: newVersion,
      phases_rerun: phasesToRerun,
      intent,
      message: `Re-ran ${phasesToRerun.join(' + ')} to apply your change.`,
    };
  }, [versions, currentVersion]);

  const handleRevert = useCallback((version) => {
    const v = versions.find((x) => x.version === version);
    if (!v) return;
    setCurrentVersion(version);
    setVideoUrl('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4');
  }, [versions]);

  // Derived: which mini-phase is "active" in overlay
  const activeMini = (() => {
    if (phases.story.status === 'running') return 'story';
    if (phases.audio.status === 'running') return 'audio';
    if (phases.video.status === 'running') return 'video';
    return null;
  })();

  const overlayMessages = {
    story: 'Drafting story structure…',
    audio: 'Casting voices and composing audio…',
    video: 'Rendering scenes and encoding video…',
  };

  // Auto-seed demo job on first load so the design isn't blank
  useEffect(() => {
    if (!tweaks.autoSeedDemo) return;
    setJobId('job_demo01x');
    setVideoUrl('https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4');
    setPrompt('A lonely lighthouse keeper befriends a glowing creature washed ashore during a winter storm.');
    setPhases({
      story: { status: 'completed', progress: 100 },
      audio: { status: 'completed', progress: 100 },
      video: { status: 'completed', progress: 100 },
    });
    setVersions([
      { version: 1, phase: 'story', note: 'Initial generation',                   created_at: Date.now() - 1000 * 60 * 4 },
      { version: 2, phase: 'audio', note: 'Make it sadder',                       created_at: Date.now() - 1000 * 60 * 3 },
      { version: 3, phase: 'video_frame', note: 'Change to night scene',          created_at: Date.now() - 1000 * 60 * 2 },
      { version: 4, phase: 'video', note: 'Add subtitles',                        created_at: Date.now() - 1000 * 60 * 1 },
    ]);
    setCurrentVersion(4);
    // eslint-disable-next-line
  }, []);

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

        {tweaks.showDemoBanner && (
          <div className="demo-banner">
            <span className="pip" />
            DEMO MODE · pipeline is simulated · type a prompt and press Generate to watch it run
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
          ANIMORA <span className="sep">·</span> v0.4 PREVIEW <span className="sep">·</span> RENDER PIPELINE BUILD 26.05
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
              {['story', 'audio', 'video'].map((p) => {
                const ph = phases[p];
                const cls = ph.status === 'completed'
                  ? 'mini-phase done'
                  : ph.status === 'running'
                    ? 'mini-phase active'
                    : 'mini-phase';
                return (
                  <div key={p} className={cls}>
                    <span className="pip" />
                    <span style={{ textTransform: 'capitalize' }}>{p}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {window.TweaksPanel && (
        <window.TweaksPanel title="Tweaks">
          <window.TweakSection title="Demo">
            <window.TweakToggle
              label="Show demo banner"
              value={tweaks.showDemoBanner}
              onChange={(v) => setTweak('showDemoBanner', v)}
            />
            <window.TweakToggle
              label="Auto-seed demo job"
              value={tweaks.autoSeedDemo}
              onChange={(v) => setTweak('autoSeedDemo', v)}
            />
          </window.TweakSection>
        </window.TweaksPanel>
      )}
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
