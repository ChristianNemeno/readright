from typing import Optional

from pydantic import BaseModel, Field


class Passage(BaseModel):
    id: str
    title: str
    grade_level: int
    language: str
    set: str
    cycle: str
    word_count: int
    text: str


class PassageSummary(BaseModel):
    id: str
    title: str
    grade_level: int
    language: str
    set: str
    cycle: str
    word_count: int


class MiscueRecord(BaseModel):
    target: str
    spoken: Optional[str] = None
    type: str
    start: Optional[float] = None
    end: Optional[float] = None
    counts_as_major_miscue: Optional[bool] = None


class AssessmentResponse(BaseModel):
    passage_id: str
    transcript: str = ""
    wpm: Optional[float] = None
    word_recognition_pct: Optional[float] = None
    reading_level: Optional[str] = None
    miscues: list[MiscueRecord] = Field(default_factory=list)
    total_words: int
    major_miscue_count: int = 0
    reading_time_seconds: Optional[float] = None
