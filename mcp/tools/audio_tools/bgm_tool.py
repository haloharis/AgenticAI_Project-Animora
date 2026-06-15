from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Any, Dict

import numpy as np
from pydub import AudioSegment

from mcp.base_tool import BaseTool, ToolOutput
from shared.constants.constants import MOOD_BGM_FREQ
from shared.utils.helpers import ensure_dirs

logger = logging.getLogger(__name__)

_BGM_DIR = os.path.normpath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "..", "data", "bgm")
)


def _get_ffmpeg_exe() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _mp3_to_audiosegment(mp3_path: str) -> AudioSegment | None:
    """Convert MP3 → temp WAV via imageio_ffmpeg subprocess, then load with pydub natively.
    This bypasses pydub's own ffmpeg discovery which is unreliable on Windows."""
    ffmpeg_exe = _get_ffmpeg_exe()
    if not ffmpeg_exe:
        logger.warning("[bgm_tool] imageio_ffmpeg not available, cannot decode MP3")
        return None

    fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        result = subprocess.run(
            [ffmpeg_exe, "-y", "-i", mp3_path, "-ar", "44100", "-ac", "2", tmp_wav],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning(f"[bgm_tool] ffmpeg MP3→WAV failed: {result.stderr.decode(errors='ignore')}")
            return None
        audio = AudioSegment.from_wav(tmp_wav)
        return audio
    except Exception as e:
        logger.warning(f"[bgm_tool] MP3 decode failed for {mp3_path}: {e}")
        return None
    finally:
        try:
            os.unlink(tmp_wav)
        except OSError:
            pass


def _load_real_bgm(mood: str, duration_ms: int) -> AudioSegment | None:
    """Load a real BGM file, loop/trim to duration_ms. Returns None if not found or on error."""
    for ext in ("mp3", "wav"):
        path = os.path.join(_BGM_DIR, f"{mood}.{ext}")
        if not os.path.exists(path):
            continue
        try:
            logger.info(f"[bgm_tool] Loading BGM from {path}")
            if ext == "mp3":
                audio = _mp3_to_audiosegment(path)
            else:
                audio = AudioSegment.from_wav(path)

            if audio is None:
                continue

            audio = audio.set_frame_rate(44100).set_channels(2)
            if len(audio) < duration_ms:
                loops = (duration_ms // len(audio)) + 1
                audio = audio * loops
            return audio[:duration_ms]
        except Exception as e:
            logger.warning(f"[bgm_tool] Failed to load {path}: {e}")

    logger.warning(f"[bgm_tool] No BGM file found for mood '{mood}' in {_BGM_DIR}")
    return None


def _synthesize_bgm(mood: str, duration_ms: int) -> AudioSegment:
    """Fallback: generate ambient tone via sine wave synthesis."""
    freq = MOOD_BGM_FREQ.get(mood, 432)
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, num_samples, dtype=np.float32)

    wave = (
        np.sin(2 * np.pi * freq * t) * 0.5
        + np.sin(2 * np.pi * freq * 1.5 * t) * 0.25
        + np.sin(2 * np.pi * freq * 2.0 * t) * 0.15
    )
    pcm = (wave * 32767).astype(np.int16)

    return AudioSegment(pcm.tobytes(), frame_rate=sample_rate, sample_width=2, channels=1)


class BGMTool(BaseTool):
    name = "bgm_tool"
    description = "Generate ambient background music from real audio files with sine-wave fallback"

    def execute(self, inputs: Dict[str, Any]) -> ToolOutput:
        mood: str = inputs.get("mood", "calm")
        duration_ms: int = inputs["duration_ms"]
        output_path: str = inputs["output_path"]

        ensure_dirs(os.path.dirname(output_path) or ".")

        audio = _load_real_bgm(mood, duration_ms)
        if audio is None:
            logger.info(f"[bgm_tool] Falling back to sine-wave synthesis for mood '{mood}'")
            audio = _synthesize_bgm(mood, duration_ms)

        audio = audio.fade_in(500).fade_out(800)
        audio.export(output_path, format="wav")
        logger.info(f"[bgm_tool] BGM written to {output_path} ({len(audio)} ms)")

        return ToolOutput(success=True, data={"path": output_path, "duration_ms": len(audio)})
