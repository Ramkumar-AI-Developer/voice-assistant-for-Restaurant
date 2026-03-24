"""
Speech-to-Text via Groq Whisper (whisper-large-v3-turbo).

Uses the official Groq Python SDK with AsyncGroq for non-blocking I/O.
Accepts raw audio bytes (wav / mp3 / ogg / flac / webm).

Latency notes:
  • whisper-large-v3-turbo is Groq's fastest Whisper variant (~200-400 ms)
  • language="en" skips language-detection overhead
  • A short vocabulary prompt improves accuracy on food/menu terms
"""

import io
import logging
import time
from typing import Optional

from groq import AsyncGroq

from app.config import settings

logger = logging.getLogger(__name__)

# Shared async client — one instance for the process lifetime
_client: Optional[AsyncGroq] = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _client


# Vocabulary hint fed to Whisper as a prompt — improves menu-word accuracy
_MENU_VOCAB_HINT = (
    "Garlic Bread, Caesar Salad, Classic Burger, Grilled Chicken, "
    "Margherita Pizza, Pasta Arrabiata, Fish and Chips, Veggie Wrap, "
    "Chocolate Lava Cake, Cheesecake, Ice Cream, Soft Drink, Fresh Juice, "
    "Sparkling Water, House Wine, Beer, Coffee, Latte, Cappuccino"
)


async def transcribe_audio(
    audio_bytes: bytes,
    audio_format: str = "wav",   # wav | mp3 | ogg | flac | webm
    language: str = "en",
) -> tuple[str, float]:
    """
    Transcribe audio bytes with Groq Whisper.

    Returns:
        (transcript_text, latency_seconds)

    Raises:
        RuntimeError on API / network errors.
    """
    if not audio_bytes:
        return "", 0.0

    client = _get_client()
    t0 = time.perf_counter()

    # Groq SDK expects a file-like tuple: (filename, bytes_io, mime_type)
    audio_file = (f"audio.{audio_format}", io.BytesIO(audio_bytes), f"audio/{audio_format}")

    try:
        transcription = await client.audio.transcriptions.create(
            file=audio_file,
            model=settings.GROQ_STT_MODEL,          # whisper-large-v3-turbo
            language=language,
            prompt=_MENU_VOCAB_HINT,                 # vocabulary boost
            response_format="json",
            temperature=0.0,                         # deterministic output
        )
        latency = time.perf_counter() - t0
        transcript = transcription.text.strip()
        logger.info(f"STT [{latency:.2f}s] '{transcript[:80]}'")
        return transcript, latency

    except Exception as exc:
        latency = time.perf_counter() - t0
        logger.error(f"Groq STT error after {latency:.2f}s: {exc}")
        raise RuntimeError(f"STT failed: {exc}") from exc


async def close() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
