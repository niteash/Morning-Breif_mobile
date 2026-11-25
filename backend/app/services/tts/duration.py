import math

from mutagen.mp3 import MP3


def audio_duration_seconds(path: str) -> int:
    """Read encoded MP3 frames, rejecting empty or invalid audio before upload."""
    duration = MP3(path).info.length
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Generated audio has no valid duration")
    return math.ceil(duration)
