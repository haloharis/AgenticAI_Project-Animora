import warnings

# Suppress the harmless "Couldn't find ffmpeg" warning that pydub emits at class
# definition time. imageio-ffmpeg bundles ffmpeg; pydub just can't find it via PATH.
warnings.filterwarnings(
    "ignore",
    message="Couldn't find ffmpeg or avconv",
    category=RuntimeWarning,
)

try:
    import imageio_ffmpeg
    from pydub import AudioSegment

    _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    AudioSegment.converter = _ffmpeg_exe
    AudioSegment.ffmpeg = _ffmpeg_exe
    AudioSegment.ffprobe = _ffmpeg_exe
except Exception:
    pass
