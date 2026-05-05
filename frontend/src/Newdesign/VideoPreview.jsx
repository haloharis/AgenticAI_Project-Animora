function VideoPreview({ videoUrl, jobId }) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(videoUrl || window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch (e) {
      setCopied(false);
    }
  };

  const handleDownload = () => {
    if (!videoUrl) return;
    const a = document.createElement('a');
    a.href = videoUrl;
    a.download = `animora-${jobId || 'video'}.mp4`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="card video-card">
      <div className="card-header">
        <h3 className="card-title">
          <span className="icon">▶</span>
          Preview
        </h3>
        {jobId && (
          <span className="card-subtitle" style={{ margin: 0, fontSize: 12, fontFamily: "'JetBrains Mono', monospace" }}>
            job · {jobId.slice(0, 8)}
          </span>
        )}
      </div>

      <div className="video-frame">
        {videoUrl ? (
          <video src={videoUrl} controls poster="" />
        ) : (
          <div className="video-empty">
            <div className="video-empty-inner">
              <div className="play-glyph">▶</div>
              <div className="label">Awaiting Render</div>
              <div className="msg">Your animated short will appear here once the pipeline finishes.</div>
            </div>
          </div>
        )}
      </div>

      <div className="video-actions">
        <button
          className="action-btn primary"
          onClick={handleDownload}
          disabled={!videoUrl}
        >
          <span>↓</span> Download MP4
        </button>
        <button
          className="action-btn"
          onClick={handleCopy}
          disabled={!videoUrl}
        >
          {copied ? (
            <><span className="copied">✓</span> Link copied</>
          ) : (
            <><span>⎘</span> Share link</>
          )}
        </button>
      </div>
    </div>
  );
}

window.VideoPreview = VideoPreview;
