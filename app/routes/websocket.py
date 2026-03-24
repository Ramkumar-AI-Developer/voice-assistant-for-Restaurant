"""
WebSocket handler: Twilio Media Stream ←→ OpenAI Realtime API bridge.

Architecture:
  Caller ↔ Twilio (g711_ulaw) ↔ /media-stream ↔ OpenAI Realtime API (g711_ulaw)

Key benefits over Gemini Live API:
  • OpenAI natively supports g711_ulaw — zero audio resampling
  • Built-in server-side VAD that works with telephony audio
  • Barge-in / interruption handling out of the box
  • Sub-second latency
"""

import json
import asyncio
import logging

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.models.menu import get_menu_text

router = APIRouter()
logger = logging.getLogger(__name__)

# OpenAI Realtime API endpoint
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"

# System instructions for the voice assistant
SYSTEM_MESSAGE = """You are Aria, a friendly and efficient voice assistant for "The Golden Fork" restaurant.
Your job is to help callers place food orders over the phone.

RULES:
- Keep every reply short and natural — this is a phone call, not a chat.
- Be warm but quick. No long monologues.
- Always confirm the item name and price when adding something to the order.
- If you are unsure what the caller said, ask ONE short clarifying question.
- When the caller is done ordering, ask for their NAME.
- After getting the name, ask if it's for pickup or delivery.
- Then read back the full order with the total and ask for confirmation.
- Do NOT invent items not on the menu. Politely say the item is unavailable.
- The caller's phone number is automatically captured — do NOT ask for it.

MENU:
{menu}
"""


@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Bridge Twilio's bidirectional audio stream with OpenAI's Realtime API."""
    await websocket.accept()
    logger.info("Twilio WebSocket connected on /media-stream")

    stream_sid = None
    call_sid = None

    # OpenAI Realtime API connection headers
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        async with websockets.connect(
            OPENAI_REALTIME_URL,
            additional_headers=headers,
            close_timeout=10,
        ) as openai_ws:
            logger.info("Connected to OpenAI Realtime API")

            # ── Configure session ─────────────────────────────────────────
            menu_text = get_menu_text()
            session_config = {
                "type": "session.update",
                "session": {
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                    },
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "voice": "shimmer",
                    "instructions": SYSTEM_MESSAGE.format(menu=menu_text),
                    "modalities": ["text", "audio"],
                    "temperature": 0.8,
                    "input_audio_transcription": {
                        "model": "whisper-1",
                    },
                }
            }
            await openai_ws.send(json.dumps(session_config))
            logger.info("Sent session config to OpenAI")

            # ── Send initial greeting trigger ─────────────────────────────
            greeting_event = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": "Greet the caller warmly and ask what they would like to order today. Keep it under 20 words.",
                }
            }
            await openai_ws.send(json.dumps(greeting_event))
            logger.info("Sent greeting trigger to OpenAI")

            # ── Twilio → OpenAI (forward caller audio) ───────────────────
            async def twilio_to_openai():
                nonlocal stream_sid, call_sid
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        event = data.get("event")

                        if event == "start":
                            stream_sid = data["start"]["streamSid"]
                            call_sid = data["start"]["callSid"]
                            logger.info(f"Stream started: {stream_sid} call={call_sid}")

                        elif event == "media":
                            # Forward audio directly — both use g711_ulaw, no conversion!
                            audio_event = {
                                "type": "input_audio_buffer.append",
                                "audio": data["media"]["payload"],
                            }
                            await openai_ws.send(json.dumps(audio_event))

                        elif event == "stop":
                            logger.info(f"Twilio stream stopped")
                            break

                except WebSocketDisconnect:
                    logger.info("Twilio WebSocket disconnected")
                except websockets.exceptions.ConnectionClosed:
                    logger.info("OpenAI connection closed during send")
                except Exception as e:
                    logger.error(f"Twilio→OpenAI error: {e}")

            # ── OpenAI → Twilio (forward assistant audio) ────────────────
            async def openai_to_twilio():
                nonlocal stream_sid
                audio_chunks_sent = 0
                try:
                    async for message in openai_ws:
                        response = json.loads(message)
                        event_type = response.get("type", "")

                        # ── Audio response chunk ──────────────────────────
                        if event_type == "response.audio.delta" and stream_sid:
                            audio_payload = response.get("delta", "")
                            if audio_payload:
                                await websocket.send_json({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": audio_payload},
                                })
                                audio_chunks_sent += 1

                        # ── User interrupted (barge-in) ──────────────────
                        elif event_type == "input_audio_buffer.speech_started":
                            logger.info("User interruption detected — clearing Twilio buffer")
                            if stream_sid:
                                await websocket.send_json({
                                    "event": "clear",
                                    "streamSid": stream_sid,
                                })
                            audio_chunks_sent = 0

                        # ── Audio response complete ──────────────────────
                        elif event_type == "response.audio.done":
                            logger.info(f"Audio response complete ({audio_chunks_sent} chunks sent)")
                            audio_chunks_sent = 0

                        # ── Transcript logging ───────────────────────────
                        elif event_type == "response.audio_transcript.done":
                            transcript = response.get("transcript", "")
                            logger.info(f"🤖 Assistant: {transcript[:120]}")

                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            transcript = response.get("transcript", "")
                            logger.info(f"👤 User: {transcript[:120]}")

                        # ── Session events ───────────────────────────────
                        elif event_type == "session.created":
                            logger.info("OpenAI session created")

                        elif event_type == "session.updated":
                            logger.info("OpenAI session configured")

                        elif event_type == "response.done":
                            usage = response.get("response", {}).get("usage", {})
                            if usage:
                                logger.info(f"Tokens: input={usage.get('input_tokens', 0)} output={usage.get('output_tokens', 0)}")

                        # ── Error handling ────────────────────────────────
                        elif event_type == "error":
                            error_info = response.get("error", {})
                            logger.error(f"OpenAI error: {error_info.get('message', response)}")

                except websockets.exceptions.ConnectionClosed:
                    logger.info("OpenAI WebSocket closed")
                except Exception as e:
                    logger.error(f"OpenAI→Twilio error: {e}")

            # ── Run both directions concurrently ─────────────────────────
            await asyncio.gather(
                twilio_to_openai(),
                openai_to_twilio(),
            )

    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"Failed to connect to OpenAI Realtime API: {e}")
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}", exc_info=True)
    finally:
        logger.info(f"Media stream session ended (call={call_sid})")
