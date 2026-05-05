const STYLES = [
  { id: 'cinematic', label: 'Cinematic', emoji: '🎬' },
  { id: 'fantasy',   label: 'Fantasy',   emoji: '🧙' },
  { id: 'horror',    label: 'Horror',    emoji: '👻' },
  { id: 'comedy',    label: 'Comedy',    emoji: '😂' },
  { id: 'sci-fi',    label: 'Sci-Fi',    emoji: '🚀' },
  { id: 'romance',   label: 'Romance',   emoji: '💕' },
];

function PromptInput({ prompt, setPrompt, style, setStyle, onSubmit, isGenerating }) {
  const max = 500;
  const handleSubmit = (e) => {
    e.preventDefault();
    if (!prompt.trim() || isGenerating) return;
    onSubmit();
  };

  return (
    <form className="card prompt-card" onSubmit={handleSubmit}>
      <div className="card-header">
        <h3 className="card-title">
          <span className="icon">✨</span>
          Your Story
        </h3>
        <span className="card-subtitle" style={{ margin: 0, fontSize: 12 }}>
          Step 1 of 2
        </span>
      </div>

      <div className="prompt-textarea-wrap">
        <textarea
          className="prompt-textarea"
          placeholder="A lonely lighthouse keeper discovers a glowing creature washed ashore during a winter storm…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value.slice(0, max))}
          disabled={isGenerating}
        />
        <div className="prompt-counter">{prompt.length}/{max}</div>
      </div>

      <div className="style-label">Choose a Style</div>
      <div className="style-pills">
        {STYLES.map((s) => (
          <button
            type="button"
            key={s.id}
            className={`style-pill ${style === s.id ? 'active' : ''}`}
            onClick={() => !isGenerating && setStyle(s.id)}
            disabled={isGenerating}
          >
            <span className="emoji">{s.emoji}</span>
            <span>{s.label}</span>
          </button>
        ))}
      </div>

      <button
        type="submit"
        className={`generate-btn ${isGenerating ? 'is-loading' : ''}`}
        disabled={isGenerating || !prompt.trim()}
      >
        {isGenerating ? (
          <>
            <span className="spinner" />
            Generating Your Film…
          </>
        ) : (
          <>
            Generate Video
            <span className="arrow-icon">→</span>
          </>
        )}
      </button>
    </form>
  );
}

window.PromptInput = PromptInput;
