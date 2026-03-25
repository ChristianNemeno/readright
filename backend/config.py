import os
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
DEFAULT_DEVICE = "cpu"


def _env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def get_whisper_model_name() -> str:
    return os.getenv("PHILIRI_WHISPER_MODEL", DEFAULT_WHISPER_MODEL)


def get_runtime_device() -> str:
    return os.getenv("PHILIRI_DEVICE", DEFAULT_DEVICE)


def get_model_cache_dir() -> str | None:
    return os.getenv("PHILIRI_MODEL_CACHE_DIR")


def get_whisper_language() -> str | None:
    return os.getenv("PHILIRI_WHISPER_LANGUAGE")


def get_align_model_name() -> str | None:
    return os.getenv("PHILIRI_ALIGN_MODEL")


def use_local_models_only() -> bool:
    return _env_flag("PHILIRI_LOCAL_MODELS_ONLY", default=False)
