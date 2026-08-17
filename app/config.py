"""
Centralised configuration.
All secrets are loaded from environment variables / .env file.

Security: No working defaults for secrets. Pydantic raises
ValidationError at startup if any required var is missing —
making the insecure state impossible, not merely discouraged.
"""

import secrets
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Twilio ────────────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str

    # ── OpenAI Realtime ───────────────────────────────────────────────────────
    OPENAI_API_KEY: str                    # Required — no default

    # ── App ───────────────────────────────────────────────────────────────────
    BASE_URL: str                          # Public HTTPS URL for Twilio callbacks
    SECRET_KEY: str                        # Required — no default
    LOG_LEVEL: str = "INFO"

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── JWT Auth ──────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str                    # Required — no default
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480          # 8 hours

    # ── Default Admin ─────────────────────────────────────────────────────────
    # If not set, a random password is generated at first boot and printed once.
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = ""       # Empty = auto-generate on first boot

    # ── Twilio TTS ────────────────────────────────────────────────────────────
    TWILIO_VOICE: str = "Google.en-GB-Neural2-A"
    TWILIO_LANGUAGE: str = "en-GB"

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    TWILIO_WHATSAPP_FROM: str = ""         # e.g. whatsapp:+14155238886
    COOK_WHATSAPP_NUMBER: str = ""         # Required if WhatsApp notifications are desired

    # ── Session ───────────────────────────────────────────────────────────────
    SESSION_TTL_SECONDS: int = 1800        # 30 min
    MAX_RECORD_SECONDS: int = 15

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
