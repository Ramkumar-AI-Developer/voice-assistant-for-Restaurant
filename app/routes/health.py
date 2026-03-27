"""
Health check endpoint with database connectivity test.
"""

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.database import AsyncSessionLocal

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

    return {
        "status": "ok",
        "database": db_status,
        "version": "2.1.0",
    }
