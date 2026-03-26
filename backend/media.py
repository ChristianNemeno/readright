import os
import shutil
import subprocess
from pathlib import Path

# Ensure ffmpeg is findable even if PATH wasn't updated before this process started
_FFMPEG_FALLBACK = r"C:\Nemeno\ffmpeg-2026-03-22-git-9c63742425-essentials_build\bin"
if _FFMPEG_FALLBACK not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _FFMPEG_FALLBACK + os.pathsep + os.environ.get("PATH", "")

from fastapi import HTTPException, UploadFile, status

from backend.config import ALLOWED_UPLOAD_EXTENSIONS


class AudioProcessingError(RuntimeError):
    """Base error for upload and normalization failures."""


class UnsupportedMediaTypeError(AudioProcessingError):
    """Raised when an uploaded file extension is not accepted."""


class FfmpegUnavailableError(AudioProcessingError):
    """Raised when ffmpeg is not installed or not on PATH."""


class MediaNormalizationError(AudioProcessingError):
    """Raised when ffmpeg fails to normalize the upload."""


def validate_upload_extension(filename: str | None) -> str:
    if not filename:
        raise UnsupportedMediaTypeError("Uploaded file must include a filename.")

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed_types = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise UnsupportedMediaTypeError(
            f"Unsupported file type '{suffix or 'unknown'}'. Allowed types: {allowed_types}."
        )
    return suffix


async def save_upload_file(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("wb") as output_file:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            output_file.write(chunk)

    await upload.close()


def normalize_media_to_wav(source_path: Path, normalized_wav_path: Path) -> None:
    normalized_wav_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise FfmpegUnavailableError(
            "ffmpeg is required to normalize uploaded media, but it was not found on PATH."
        )

    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(source_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(normalized_wav_path),
    ]

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise MediaNormalizationError(
            "ffmpeg failed to normalize the uploaded media. "
            f"stderr: {result.stderr.strip()}"
        )


def to_http_exception(error: AudioProcessingError) -> HTTPException:
    if isinstance(error, UnsupportedMediaTypeError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    if isinstance(error, FfmpegUnavailableError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))

    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
