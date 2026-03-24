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

from app.database import get_db
from app.services.session_store import SessionStore
from app.services.llm_service import generate_greeting, build_system_prompt
from app.services.twiml_service import greeting_twiml, error_twiml
from app.models.menu import get_menu_text
from app.models.db_models import CallLog

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/inbound")
async def inbound_call(
    request: Request,
    CallSid:  str = Form(...),
    From:     str = Form(default="unknown"),
    To:       str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Inbound call  SID={CallSid}  from={From}  to={To}")

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

        # Store system prompt as first "message" so it's always at index 0
        menu_text     = get_menu_text()
        system_prompt = build_system_prompt(menu_text)
        session.add_message("system", system_prompt)

        # LLM-generated greeting (streamed, ~300-600 ms)
        greeting_text = await generate_greeting(menu_text)
        session.add_message("assistant", greeting_text)

        twiml = greeting_twiml(greeting_text)
        return Response(content=twiml, media_type="application/xml")

    except Exception as exc:
        logger.error(f"Error on inbound call {CallSid}: {exc}", exc_info=True)
        return Response(content=error_twiml(), media_type="application/xml")
