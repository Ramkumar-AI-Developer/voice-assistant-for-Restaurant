"""
Twilio webhook handlers — the core conversation loop.

Endpoints:
  POST /webhook/speech          — main speech result handler
  POST /webhook/partial         — barge-in / in-progress speech (no TwiML response)
  POST /webhook/confirm         — yes / no order confirmation
  POST /webhook/speech_fallback — silence / no-input fallback
  POST /webhook/status          — call lifecycle events (completed, failed, …)
"""

import logging

import httpx
from fastapi import APIRouter, Form, Request, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.session_store import SessionStore
from app.services.stt_service import transcribe_audio
from app.services.llm_service import process_utterance, build_system_prompt
from app.services.order_service import apply_actions, save_order_to_db, save_call_log
from app.services.twiml_service import (
    listen_twiml,
    silence_twiml,
    confirm_order_twiml,
    order_placed_twiml,
    cancelled_twiml,
    error_twiml,
)
from app.models.menu import get_menu_text
from app.models.session import CallStage
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Silence re-prompts — cycle through these so the caller doesn't hear the same line
_SILENCE_PROMPTS = [
    "I didn't catch that. What would you like to order?",
    "Still there? Go ahead and tell me what you'd like.",
    "I'm having trouble hearing you. Please tell me your order.",
]
_MAX_SILENCE = 3     # hang up after this many consecutive silent turns
_MAX_ERRORS  = 3     # hang up after this many consecutive processing errors


# ── /webhook/speech ───────────────────────────────────────────────────────────

@router.post("/speech")
async def speech_result(
    request: Request,
    CallSid:      str = Form(...),
    From:         str = Form(default="unknown"),
    SpeechResult: str = Form(default=""),
    Confidence:   str = Form(default="0"),
    RecordingUrl: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    """
    Main conversation handler.

    Twilio sends SpeechResult (its own STT) plus optionally a RecordingUrl.
    Strategy:
      1. Use Twilio STT if confidence >= 0.75 (fast path, zero extra API call)
      2. Otherwise fetch the recording and run Groq Whisper (higher accuracy)
    """
    session = await SessionStore.get_or_create(CallSid, phone_number=From)
    logger.info(f"[{CallSid}] speech — result='{SpeechResult[:80]}' conf={Confidence}")

    # ── Step 1: get best available transcript ─────────────────────────────────
    transcript = SpeechResult.strip()
    confidence = float(Confidence) if Confidence else 0.0

    if RecordingUrl and (confidence < 0.75 or not transcript):
        try:
            audio_bytes = await _fetch_recording(RecordingUrl)
            if audio_bytes:
                whisper_text, stt_latency = await transcribe_audio(audio_bytes, audio_format="wav")
                if whisper_text:
                    transcript = whisper_text
                    logger.info(f"[{CallSid}] Groq Whisper override [{stt_latency:.2f}s]: '{transcript[:80]}'")
        except Exception as exc:
            logger.warning(f"[{CallSid}] Groq Whisper fallback failed: {exc}")

    # ── Step 2: silence / empty speech check ─────────────────────────────────
    if not transcript:
        session.silence_count += 1
        if session.silence_count >= _MAX_SILENCE:
            logger.info(f"[{CallSid}] Max silence reached — hanging up")
            # Save call log before deleting session
            try:
                await save_call_log(session, db)
            except Exception as exc:
                await db.rollback()
                logger.error(f"Failed to save call log: {exc}")
            await SessionStore.delete(CallSid)
            return Response(
                content=error_twiml("We couldn't hear you. Please call back when you're ready. Goodbye!"),
                media_type="application/xml",
            )
        prompt = _SILENCE_PROMPTS[min(session.silence_count - 1, len(_SILENCE_PROMPTS) - 1)]
        return Response(content=silence_twiml(prompt), media_type="application/xml")

    session.silence_count = 0
    session.add_message("user", transcript)

    # ── Step 3: LLM — extract actions + generate spoken reply ────────────────
    try:
        menu_text     = get_menu_text()
        system_prompt = build_system_prompt(menu_text)
        llm_messages  = session.messages_for_llm(system_prompt)

        result  = await process_utterance(llm_messages, transcript)
        actions = result.get("actions", [])
        reply   = result.get("reply", "Sorry, could you repeat that?")

        # Mutate session order state
        apply_actions(session, actions)
        session.add_message("assistant", reply)
        session.error_count = 0

        logger.info(
            f"[{CallSid}] stage={session.stage.value} "
            f"items={len(session.order_items)} "
            f"total=${session.order_total:.2f} "
            f"llm_latency={result.get('latency', 0):.2f}s"
        )

    except Exception as exc:
        logger.error(f"[{CallSid}] LLM processing error: {exc}", exc_info=True)
        session.error_count += 1
        if session.error_count >= _MAX_ERRORS:
            try:
                await save_call_log(session, db)
            except Exception:
                await db.rollback()
            await SessionStore.delete(CallSid)
            return Response(content=error_twiml(), media_type="application/xml")
        return Response(
            content=listen_twiml("I'm sorry, I had a small hiccup. Could you say that again?"),
            media_type="application/xml",
        )

    # ── Step 4: route to the right TwiML based on stage ──────────────────────
    if session.stage == CallStage.COMPLETED:
        # Save order and call log to database
        try:
            order_id = await save_order_to_db(session, db)
            await save_call_log(session, db, order_id=order_id)
        except Exception as exc:
            await db.rollback()
            logger.error(f"[{CallSid}] DB save error: {exc}", exc_info=True)

        twiml = order_placed_twiml(session.order_total)
        await SessionStore.delete(CallSid)

    elif session.stage == CallStage.ABANDONED:
        try:
            await save_call_log(session, db)
        except Exception as exc:
            await db.rollback()
            logger.error(f"[{CallSid}] DB save error: {exc}")
        twiml = cancelled_twiml()
        await SessionStore.delete(CallSid)

    elif _wants_confirmation(actions):
        # LLM decided it's time to confirm — read back the order
        twiml = confirm_order_twiml(session.order_summary_text())

    else:
        twiml = listen_twiml(reply)

    return Response(content=twiml, media_type="application/xml")


# ── /webhook/partial ──────────────────────────────────────────────────────────

@router.post("/partial")
async def partial_speech(
    request: Request,
    CallSid:             str = Form(...),
    UnstableSpeechResult: str = Form(default=""),
):
    """
    Fires while the caller is still speaking (barge-in detection).
    We store the partial for context but Twilio ignores the response body.
    """
    session = await SessionStore.get(CallSid)
    if session:
        session.last_partial = UnstableSpeechResult
    logger.debug(f"[{CallSid}] partial: '{UnstableSpeechResult[:60]}'")
    return Response(status_code=200)   # body ignored by Twilio


# ── /webhook/confirm ──────────────────────────────────────────────────────────

@router.post("/confirm")
async def confirm_order(
    request: Request,
    CallSid:      str = Form(...),
    SpeechResult: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Handle the caller's yes/no response to the order confirmation."""
    session = await SessionStore.get_or_create(CallSid)
    speech  = SpeechResult.strip().lower()
    logger.info(f"[{CallSid}] confirm response: '{speech}'")

    _YES = {"yes", "yeah", "yep", "yup", "correct", "right", "confirm",
            "place", "go ahead", "sure", "ok", "okay", "sounds good", "perfect"}
    _NO  = {"no", "nope", "wait", "change", "modify", "actually",
            "cancel", "different", "wrong", "not right"}

    if any(w in speech for w in _YES):
        session.stage = CallStage.COMPLETED
        # Save order and call log to database
        try:
            order_id = await save_order_to_db(session, db)
            await save_call_log(session, db, order_id=order_id)
        except Exception as exc:
            await db.rollback()
            logger.error(f"[{CallSid}] DB save error: {exc}", exc_info=True)
        twiml = order_placed_twiml(session.order_total)
        await SessionStore.delete(CallSid)

    elif any(w in speech for w in _NO):
        reply = "No problem! What would you like to change?"
        session.add_message("assistant", reply)
        twiml = listen_twiml(reply)

    else:
        # Unclear — repeat the summary
        twiml = confirm_order_twiml(session.order_summary_text())

    return Response(content=twiml, media_type="application/xml")


# ── /webhook/speech_fallback ──────────────────────────────────────────────────

@router.post("/speech_fallback")
async def speech_fallback(
    request: Request,
    CallSid: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Catch-all for silence / errors from <Gather> actionOnEmptyResult."""
    session = await SessionStore.get_or_create(CallSid)
    session.silence_count += 1
    if session.silence_count >= _MAX_SILENCE:
        try:
            await save_call_log(session, db)
        except Exception:
            await db.rollback()
        await SessionStore.delete(CallSid)
        return Response(
            content=error_twiml("We couldn't hear you. Please call back. Goodbye!"),
            media_type="application/xml",
        )
    prompt = _SILENCE_PROMPTS[min(session.silence_count - 1, len(_SILENCE_PROMPTS) - 1)]
    return Response(content=silence_twiml(prompt), media_type="application/xml")


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
        # Save call log if session exists
        session = await SessionStore.get(CallSid)
        if session:
            try:
                await save_call_log(session, db)
            except Exception as exc:
                await db.rollback()
                logger.error(f"[{CallSid}] Failed to save call log on status: {exc}")
        await SessionStore.delete(CallSid)
    return Response(status_code=204)


# ── Private helpers ───────────────────────────────────────────────────────────

def _wants_confirmation(actions: list[dict]) -> bool:
    return any(a.get("type") == "confirm" for a in actions)


async def _fetch_recording(recording_url: str) -> bytes:
    """Download Twilio recording audio as raw bytes (wav)."""
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(
            recording_url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            headers={"Accept": "audio/wav"},
            follow_redirects=True,
        )
    if response.status_code == 200:
        return response.content
    logger.warning(f"Recording fetch failed: {response.status_code} {recording_url}")
    return b""
