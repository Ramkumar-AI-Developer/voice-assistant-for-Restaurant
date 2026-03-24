"""
POST /call/inbound
Twilio calls this URL when a new call arrives.

Configure your Twilio phone number's Voice webhook to:
    POST https://<your-domain>/call/inbound

Flow:
  1. Generate a greeting via Gemini text API
  2. Speak it with Twilio TTS inside a <Gather>
  3. <Gather> captures the caller's speech → POST /webhook/speech
  4. The conversation loop continues in webhook.py
"""

import logging

from fastapi import APIRouter, Form, Request, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import TTLCache

from app.database import get_db
from app.services.session_store import SessionStore
from app.services.llm_service import generate_greeting
from app.services.twiml_service import greeting_twiml, error_twiml
from app.models.db_models import CallLog
from app.models.menu import get_menu_text
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

        # Generate greeting via Gemini text API
        menu_text = get_menu_text()
        greeting = await generate_greeting(menu_text)
        session.add_message("assistant", greeting)
        logger.info(f"[{CallSid}] Greeting: '{greeting[:80]}'")

        # Return TwiML: Say greeting inside <Gather>, then listen
        twiml = greeting_twiml(greeting)
        return Response(content=twiml, media_type="application/xml")

    except Exception as exc:
        logger.error(f"Error on inbound call {CallSid}: {exc}", exc_info=True)
        return Response(content=error_twiml(), media_type="application/xml")
