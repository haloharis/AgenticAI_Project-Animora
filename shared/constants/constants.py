MOOD_BGM_FREQ: dict = {
    "happy": 528,
    "sad": 396,
    "tense": 741,
    "calm": 432,
    "mysterious": 285,
    "epic": 639,
    "romantic": 417,
    "horror": 174,
    "cartoon": 594,
}

KEN_BURNS_SAFETY = 1.1  # pre-scale overscan: provides pan headroom without quality loss

KEN_BURNS_PRESETS = [
    # All presets zoom IN (start ≤ end) so the eased pan becomes visible as zoom increases.
    # Pan values are source-image pixels at full zoom; clamped automatically when zoomed out.
    {"zoom_start": 1.0,  "zoom_end": 1.15, "pan_x":   0, "pan_y":   0},  # classic slow zoom
    {"zoom_start": 1.0,  "zoom_end": 1.15, "pan_x":  70, "pan_y":   0},  # zoom + drift right
    {"zoom_start": 1.0,  "zoom_end": 1.12, "pan_x":   0, "pan_y":  60},  # zoom + drift down
    {"zoom_start": 1.0,  "zoom_end": 1.12, "pan_x": -70, "pan_y":   0},  # zoom + drift left
    {"zoom_start": 1.0,  "zoom_end": 1.10, "pan_x":  55, "pan_y":  40},  # diagonal ↘
    {"zoom_start": 1.0,  "zoom_end": 1.12, "pan_x":   0, "pan_y": -60},  # zoom + drift up
    {"zoom_start": 1.0,  "zoom_end": 1.10, "pan_x": -55, "pan_y":  40},  # diagonal ↙
    {"zoom_start": 1.05, "zoom_end": 1.15, "pan_x":  80, "pan_y": -35},  # wide pan, tight zoom
]

VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 24

DEEPGRAM_VOICES = {
    "narrator": "aura-asteria-en",
    "male": "aura-orion-en",
    "female": "aura-luna-en",
    "villain": "aura-arcas-en",
    "default": "aura-asteria-en",
}

PIPELINE_PHASES = ["story", "audio", "video"]

ARK_API_URL_DEFAULT = "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"
ARK_MODEL_DEFAULT = "seedream-4-0-250828"
DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"
GROQ_MODEL_DEFAULT = "llama-3.3-70b-versatile"
