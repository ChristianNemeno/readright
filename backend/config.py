from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
PASSAGES_PATH = BACKEND_DIR / "passages" / "passages.json"

ALLOWED_UPLOAD_EXTENSIONS = {
    ".m4a",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".wav",
    ".webm",
}

DEFAULT_WHISPER_MODEL = "base"
