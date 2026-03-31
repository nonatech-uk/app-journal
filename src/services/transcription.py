"""Transcription service — OpenAI Whisper API."""

from openai import OpenAI


def transcribe_audio(file_path: str, api_key: str) -> str | None:
    """Transcribe an audio file using OpenAI Whisper API.

    Returns the transcription text, or None on failure.
    """
    if not api_key:
        return None
    try:
        client = OpenAI(api_key=api_key)
        with open(file_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        return result.text
    except Exception:
        return None
