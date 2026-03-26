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
    "Hot and Sour Veg Soup, Sweet Corn Soup, Mushroom Soup, Pepper Rasam Soup, "
    "Gobi 65, Paneer 65, Mogo 65, Mushroom 65, Paneer Tikka, Paneer Pepper Fry, "
    "Mushroom Pepper Fry, Chilly Paneer, Chilly Baby Corn, Chilly Mogo, Chilly Gobi, "
    "Veg Manchurian, Paneer Manchurian, Gobi Manchurian, Mushroom Manchurian, "
    "Veg Roll, Veg Samosa, Onion Pakoda, Vegetable Spring Roll, Plain Papadum, Masala Papadum, "
    "Chilly Idly, Cocktail Idly, Mini Podi Idly, "
    "Samosa Chaat, Panipuri, Dahi Batata Puri, Aloo Papdi Chaat, "
    "Medhu Vada, Sambar Vada, Rasa Vada, Thayir Vada, "
    "Idly, Sambar Idly, Mini Ghee Idly, Podi Idly, "
    "Ghee Pongal, Pongal and Vada, Poori Masala, Chappathi with Kurma, Parotta with Kurma, "
    "Channa Bhatura, Chilli Parotta, Kothu Parotta, "
    "Plain Dosa, Masala Dosa, Onion Dosa, Onion Masala Dosa, Ghee Roast, Ghee Masala Roast, "
    "Butter Dosa, Butter Masala Dosa, Paper Roast, Paper Masala Roast, Kal Dosa, "
    "Podi Dosa, Podi Masala Dosa, Kara Podi Dosa, Kara Podi Masala Dosa, "
    "Mysore Dosa, Mysore Masala Dosa, Paneer Masala Dosa, Mushroom Masala Dosa, "
    "Veg Masala Dosa, VV Special Dosa, Family Dosa, "
    "Rava Dosa, Rava Masala Dosa, Onion Rava Dosa, Onion Rava Masala Dosa, "
    "Plain Uthappam, Onion Uthappam, Onion Chilli Uthappam, Onion Tomato Uthappam, "
    "Chilli Coriander Uthappam, Onion Chilli Tomato Uthappam, Pizza Uthappam, Mini Uthappam, Mix Veg Uthappam, "
    "Mini Tiffin Basic, Mini Tiffin Classic, "
    "Kids Cone Dosa, Cheese Dosa, Chocolate Dosa, French Fries, "
    "South Indian Meals, North Indian Meals, Mini Meals, "
    "Sambar Rice, Bisibelabath, Curd Rice, Bagalabath, Coconut Rice, Lemon Rice, Tomato Rice, Tamarind Rice, "
    "Vegetable Dum Biryani, Mushroom Biryani, Paneer Biryani, Chef's Special Biryani, "
    "Veg Pulao, Paneer Pulao, Cashew Pulao, Jeera Pulao, Mushroom Pulao, "
    "Veg Fried Rice, Szechwan Fried Rice, Paneer Fried Rice, Chef's Special Fried Rice, Mushroom Fried Rice, "
    "Veg Noodles, Szechwan Noodles, Mushroom Noodles, "
    "Mushroom Chettinad, Bhindi Masala, Mixed Vegetable Curry, Baingan Masala, Malai Kofta, "
    "Paneer Chettinad, Kadai Paneer, Paneer Butter Masala, Paneer Tikka Masala, Paneer Shai Kurma, "
    "Palak Paneer, Paneer Burji, Paneer Jal Frieze, Mutter Paneer, "
    "Dhal Butter Fry, Dhal Makhani, Aloo Gobi Masala, Aloo Palak, Vegetable Kadai, "
    "Channa Masala, Vegetable Kurma, "
    "Plain Naan, Butter Naan, Garlic Naan, Tandoori Roti, Butter Roti, Aloo Kulcha, Paneer Kulcha, Chapathi, Parotta, "
    "Lassi, Milkshake, Strawberry, Chocolate, Vanilla, Mango, Ferrero Rocher, Oreo, "
    "Fresh Juice, Apple, ABC Juice, Orange, Carrot, Watermelon, Passion Fruit, Lime Juice, "
    "Falooda, Gulab Jamun, Kesari, Milk Cake, Payasam, Carrot Halwa, Motichoor Laddu, Kaju Sweet, "
    "Malai Kulfi, Mango Kulfi, Pistachio Kulfi, "
    "Rose Milk, Butter Milk, Soft Drinks, Mineral Water, "
    "Masala Tea, Filter Coffee, Hot Milk, Hot Badam Milk, "
    "Sweet Beeda, Curd, Raitha, Green Salad"
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
