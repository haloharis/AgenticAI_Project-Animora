import warnings

# pydub emits this at class-definition time when ffmpeg isn't on PATH.
# imageio-ffmpeg bundles the binary; pydub just can't discover it via which().
# Our audio tools set AudioSegment.converter to the bundled path after import.
warnings.filterwarnings(
    "ignore",
    message="Couldn't find ffmpeg or avconv",
    category=RuntimeWarning,
)
