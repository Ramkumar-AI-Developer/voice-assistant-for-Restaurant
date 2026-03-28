"""
Twilio webhook handlers.
Endpoints:
  POST /webhook/status — call lifecycle events (completed, failed)
"""

import logging
from fastapi import APIRouter, Form, Request, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.session_store import SessionStore
from app.services.order_service import save_call_log

logger = logging.getLogger(__name__)
router = APIRouter()

# ── /webhook/status ───────────────────────────────────────────────────────────

@router.post("/status")
async def call_status(
    request: Request,
    CallSid:    str = Form(...),
    CallStatus: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Clean up session when the call lifecycle ends."""
    logger.info(f"[{CallSid}] status={CallStatus}")
    terminal = {"completed", "failed", "busy", "no-answer", "canceled"}
    if CallStatus in terminal:
        session = await SessionStore.get(CallSid)
        if session:
            try:
                await save_call_log(session, db)
            except Exception as exc:
                await db.rollback()
                logger.error(f"[{CallSid}] Failed to save call log on status: {exc}")
        await SessionStore.delete(CallSid)
    return Response(status_code=204)
