"""
Health check endpoint with database connectivity test.
"""

import logging

from fastapi import APIRouter
from sqlalchemy import text
from google import genai
from google.genai import errors

from app.database import AsyncSessionLocal
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def health_check():
    """Basic health check with database connectivity."""
    db_status = "unknown"
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as exc:
        db_status = f"error: {str(exc)[:100]}"
        logger.error(f"Health check DB error: {exc}")

    gemini_status = "unknown"
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # Lightweight check: get model details
        await client.aio.models.get(model=settings.GEMINI_MODEL)
        gemini_status = "connected"
    except Exception as exc:
        gemini_status = f"error: {str(exc)[:100]}"
        logger.error(f"Health check Gemini error: {exc}")

    return {
        "status": "ok",
        "database": db_status,
        "gemini": gemini_status,
        "version": "2.1.0",
    }
