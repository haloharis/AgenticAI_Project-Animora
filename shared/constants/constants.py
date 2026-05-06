MOOD_BGM_FREQ: dict = {
    "happy": 528,
    "sad": 396,
    "tense": 741,
    "calm": 432,
    "mysterious": 285,
    "epic": 639,
    "romantic": 417,
}

KEN_BURNS_PRESETS = [
    {"zoom_start": 1.0, "zoom_end": 1.15, "pan_x": 0, "pan_y": 0},
    {"zoom_start": 1.1, "zoom_end": 1.0, "pan_x": 20, "pan_y": 0},
    {"zoom_start": 1.0, "zoom_end": 1.1, "pan_x": 0, "pan_y": 15},
    {"zoom_start": 1.05, "zoom_end": 1.0, "pan_x": -10, "pan_y": 0},
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

WAVESPEED_API_BASE = "https://api.wavespeed.ai/api/v3"
DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"
GROQ_MODEL_DEFAULT = "llama-3.3-70b-versatile"
