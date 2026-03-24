"""Audio conversion utilities for Twilio <-> Gemini integration."""
import base64
import audioop

# Audio constants
TWILIO_SAMPLE_RATE = 8000
GEMINI_IN_SAMPLE_RATE = 16000
GEMINI_OUT_SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2  # 16-bit PCM (2 bytes)


def twilio_to_gemini(b64_mulaw: str) -> bytes:
    """
    Decodes base64 Twilio mu-law chunk, converts to 8kHz PCM16, 
    then resamples to 16kHz PCM16 for Gemini.
    """
    mulaw_bytes = base64.b64decode(b64_mulaw)
    # Convert mu-law to 16-bit PCM at 8000Hz
    pcm8k = audioop.ulaw2lin(mulaw_bytes, SAMPLE_WIDTH)
    # Resample from 8000Hz to 16000Hz
    pcm16k, _ = audioop.ratecv(pcm8k, SAMPLE_WIDTH, 1, TWILIO_SAMPLE_RATE, GEMINI_IN_SAMPLE_RATE, None)
    return pcm16k


def gemini_to_twilio(pcm24k_bytes: bytes) -> str:
    """
    Resamples 24kHz PCM16 from Gemini to 8kHz PCM16, 
    converts to mu-law, and base64 encodes for Twilio.
    """
    # Resample from 24000Hz to 8000Hz
    pcm8k, _ = audioop.ratecv(pcm24k_bytes, SAMPLE_WIDTH, 1, GEMINI_OUT_SAMPLE_RATE, TWILIO_SAMPLE_RATE, None)
    # Convert 16-bit PCM to mu-law
    mulaw_bytes = audioop.lin2ulaw(pcm8k, SAMPLE_WIDTH)
    return base64.b64encode(mulaw_bytes).decode('ascii')
