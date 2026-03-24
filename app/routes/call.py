"""
POST /call/inbound
Twilio calls this URL when a new call arrives.

Configure your Twilio phone number's Voice webhook to:
    POST https://<your-domain>/call/inbound
"""

import logging

from fastapi import APIRouter, Form, Request, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import TTLCache

from app.database import get_db
from app.services.session_store import SessionStore
from app.services.twiml_service import error_twiml
from app.models.db_models import CallLog
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Global in-memory rate limiter: maximum 10 calls per hour per phone number
CALL_LIMIT = 10
call_rate_tracker = TTLCache(maxsize=10000, ttl=3600)

@router.post("/inbound")
async def inbound_call(
    request: Request,
    CallSid:  str = Form(...),
    From:     str = Form(default="unknown"),
    To:       str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Inbound call  SID={CallSid}  from={From}  to={To}")

    # Check caller rate limit
    current_calls = call_rate_tracker.get(From, 0)
    if current_calls >= CALL_LIMIT:
        logger.warning(f"Rate limit exceeded for caller {From}")
        twiml = error_twiml("You have reached the maximum number of calls allowed. Please try again later.")
        return Response(content=twiml, media_type="application/xml")
    
    call_rate_tracker[From] = current_calls + 1

    try:
        # Create session
        session = await SessionStore.create(call_sid=CallSid, phone_number=From)

        # Create initial call log entry in DB
        from sqlalchemy import select
        try:
            result = await db.execute(select(CallLog).where(CallLog.call_sid == CallSid))
            existing_log = result.scalar_one_or_none()
            
            if not existing_log:
                call_log = CallLog(
                    call_sid=CallSid,
                    phone_number=From,
                    status="in_progress",
                )
                db.add(call_log)
                await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error(f"Failed to create call log: {exc}")

        # Forward the call directly to our FastAPI WebSocket
        ws_url = settings.BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/media-stream"
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}" />
    </Connect>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    except Exception as exc:
        logger.error(f"Error on inbound call {CallSid}: {exc}", exc_info=True)
        return Response(content=error_twiml(), media_type="application/xml")
