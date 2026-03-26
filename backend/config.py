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


_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def get_cors_origins() -> list[str]:
    """Return allowed CORS origins.

    Set PHILIRI_CORS_ORIGINS to a comma-separated list to extend the defaults,
    e.g. "https://my-frontend-abc123-uc.a.run.app"
    """
    extra = os.getenv("PHILIRI_CORS_ORIGINS", "")
    extra_origins = [o.strip() for o in extra.split(",") if o.strip()]
    return _DEFAULT_CORS_ORIGINS + extra_origins
