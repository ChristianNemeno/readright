from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WordSegment:
    word: str
    start: float | None = None
    end: float | None = None


@dataclass(slots=True)
class TranscriptionResult:
    transcript: str
    segments: list[dict[str, Any]] = field(default_factory=list)
    words: list[WordSegment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AlignmentResult:
    words: list[WordSegment] = field(default_factory=list)
    source: str = "whisper"
    metadata: dict[str, Any] = field(default_factory=dict)
