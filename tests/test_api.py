import asyncio
import unittest
from io import BytesIO
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, UploadFile

from backend.main import assess_recording, get_passages
from backend.pipeline.types import AlignmentResult, TranscriptionResult, WordSegment
from backend.schemas import Passage


class ApiTests(unittest.TestCase):
    def test_assess_endpoint_returns_scored_payload(self) -> None:
        passage = Passage(
            id="demo_passage",
            title="Demo",
            grade_level=4,
            language="English",
            set="A",
            cycle="pre-test",
            word_count=3,
            text="The forest was",
        )
        transcription = TranscriptionResult(
            transcript="The forst was",
            segments=[{"start": 0.0, "end": 3.0}],
            words=[
                WordSegment(word="The", start=0.0, end=0.4),
                WordSegment(word="forst", start=0.5, end=1.4),
                WordSegment(word="was", start=2.0, end=3.0),
            ],
            metadata={"language": "en", "source": "whisper"},
        )
        alignment = AlignmentResult(
            words=list(transcription.words),
            source="whisperx",
            metadata={"alignment_source": "whisperx"},
        )
        upload = UploadFile(filename="sample.wav", file=BytesIO(b"fake-bytes"))

        with (
            patch("backend.main.get_passage_or_404", return_value=passage),
            patch("backend.main.save_upload_file", new=AsyncMock(return_value=None)),
            patch("backend.main.normalize_media_to_wav"),
            patch("backend.main.get_whisper_model_name", return_value="base"),
            patch("backend.main.transcribe_audio", return_value=transcription),
            patch("backend.main.force_align_words", return_value=alignment),
        ):
            response = asyncio.run(assess_recording(file=upload, passage_id=passage.id))

        payload = response.model_dump()
        self.assertEqual(payload["passage_id"], passage.id)
        self.assertEqual(payload["alignment_source"], "whisperx")
        self.assertEqual(payload["major_miscue_count"], 1)
        self.assertEqual(payload["reading_level"], "Frustration")
        self.assertEqual(payload["wpm"], 60.0)
        self.assertEqual(payload["word_recognition_pct"], 66.67)
        self.assertEqual([miscue["type"] for miscue in payload["miscues"]], ["correct", "mispronunciation", "correct"])

    def test_assess_endpoint_rejects_invalid_extension(self) -> None:
        passage = Passage(
            id="demo_passage",
            title="Demo",
            grade_level=4,
            language="English",
            set="A",
            cycle="pre-test",
            word_count=3,
            text="The forest was",
        )
        upload = UploadFile(filename="notes.txt", file=BytesIO(b"plain text"))

        with patch("backend.main.get_passage_or_404", return_value=passage):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(assess_recording(file=upload, passage_id=passage.id))

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Unsupported file type", context.exception.detail)

    def test_passages_endpoint_lists_available_passages(self) -> None:
        payload = [item.model_dump() for item in asyncio.run(get_passages())]

        self.assertGreaterEqual(len(payload), 2)
        self.assertIn("id", payload[0])
        self.assertIn("title", payload[0])


if __name__ == "__main__":
    unittest.main()
