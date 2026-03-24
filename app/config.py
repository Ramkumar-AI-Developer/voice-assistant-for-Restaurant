"""
Centralised configuration.
All secrets are loaded from environment variables / .env file.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Twilio ────────────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_API_KEY: str
    TWILIO_PHONE_NUMBER: str

    # ── Groq (STT only) ──────────────────────────────────────────────────────
    GROQ_API_KEY: str
    GROQ_STT_MODEL: str = "whisper-large-v3"

    # ── Gemini (LLM) ─────────────────────────────────────────────────────────
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # ── App ───────────────────────────────────────────────────────────────────
    BASE_URL: str                          # Public HTTPS URL for Twilio callbacks
    SECRET_KEY: str = "change-me"
    LOG_LEVEL: str = "INFO"

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── JWT Auth ──────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480          # 8 hours

    # ── Default Admin ─────────────────────────────────────────────────────────
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"

    # ── Twilio TTS ────────────────────────────────────────────────────────────
    TWILIO_VOICE: str = "Google.en-US-Journey-F"
    TWILIO_LANGUAGE: str = "en-US"

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"
    COOK_WHATSAPP_NUMBER: str = "whatsapp:+917708504240"

    # ── Session ───────────────────────────────────────────────────────────────
    SESSION_TTL_SECONDS: int = 1800        # 30 min
    MAX_RECORD_SECONDS: int = 15

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
