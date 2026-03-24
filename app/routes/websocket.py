"""
FastAPI WebSocket endpoint for Twilio Media Streams.
Connects directly to the Google Gemini Multimodal Live API.
"""

import asyncio
import json
import logging
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.menu import get_menu_text, find_menu_item, OrderItem
from app.services.session_store import SessionStore
from app.services.order_service import save_order_to_db
from app.utils.audio import twilio_to_gemini, gemini_to_twilio

logger = logging.getLogger(__name__)
router = APIRouter()

_genai_client = None

def get_genai_client():
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _genai_client


SYSTEM_INSTRUCTION = """
You are Aria, a friendly and efficient voice assistant for "The Golden Fork" restaurant.
Your job is to help callers place food orders over the phone.

MENU:
{menu_text}

STRICT RULES:
- Keep every reply under 35 words. Be brief and warm.
- Confirm the caller's items and total. Ask if they want pickup or delivery.
- You are speaking on a live phone call, so be natural and conversational.
- ALWAYS use the provided tools (add_order_item, remove_order_item, finalize_order) to manage orders.
- Do NOT think out loud! Just respond naturally.
"""

_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "add_order_item",
                "description": "Add one or more units of a specific menu item to the order.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "item_name": {"type": "STRING", "description": "The name of the item on the menu to add"},
                        "quantity": {"type": "INTEGER", "description": "Quantity to add (e.g., 2)"},
                        "notes": {"type": "STRING", "description": "Any special instructions (e.g., 'no onions')"}
                    },
                    "required": ["item_name", "quantity"]
                }
            },
            {
                "name": "remove_order_item",
                "description": "Remove an item from the order.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "item_name": {"type": "STRING", "description": "The name of the item to remove"}
                    },
                    "required": ["item_name"]
                }
            },
            {
                "name": "finalize_order",
                "description": "Call this to finalize and submit the order to the kitchen.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "customer_name": {"type": "STRING", "description": "Name of the customer"},
                        "order_type": {"type": "STRING", "description": "Must be 'pickup' or 'delivery'"}
                    },
                    "required": ["customer_name", "order_type"]
                }
            }
        ]
    }
]


@router.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("Twilio WebSocket connected on /media-stream")
    
    stream_sid = None
    call_sid = None
    client = get_genai_client()

    MODEL = "gemini-2.5-flash-native-audio-latest"

    menu_text = get_menu_text()
    prompt = SYSTEM_INSTRUCTION.format(menu_text=menu_text)

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text=prompt)]
        ),
        tools=_TOOLS,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede"
                )
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    try:
        async with client.aio.live.connect(model=MODEL, config=config) as gemini_session:
            logger.info("Connected to Gemini Live API")

            # ─── Twilio → Gemini (inbound audio) ───────────────────────────
            async def twilio_to_gemini_task():
                nonlocal stream_sid, call_sid
                audio_chunks_in = 0
                try:
                    while True:
                        try:
                            message_str = await websocket.receive_text()
                        except WebSocketDisconnect:
                            logger.info("Twilio WebSocket disconnected in receiver")
                            break
                        
                        data = json.loads(message_str)
                        event = data.get("event")
                        
                        if event == "start":
                            stream_sid = data["start"]["streamSid"]
                            call_sid = data["start"]["callSid"]
                            logger.info(f"Media Stream started: stream={stream_sid} call={call_sid}")
                            # Kick off the greeting
                            await gemini_session.send(input="Hello! Please greet the caller warmly.", end_of_turn=True)
                            logger.info("Sent greeting prompt to Gemini")
                        
                        elif event == "media":
                            b64_audio = data["media"]["payload"]
                            pcm16k_chunk = twilio_to_gemini(b64_audio)
                            try:
                                await gemini_session.send_realtime_input(
                                    audio=types.Blob(
                                        data=pcm16k_chunk,
                                        mime_type="audio/pcm;rate=16000"
                                    )
                                )
                            except Exception as send_err:
                                logger.error(f"Failed to send audio to Gemini: {send_err}")
                                break
                            audio_chunks_in += 1
                            if audio_chunks_in % 200 == 0:
                                logger.info(f"Audio in: {audio_chunks_in} chunks forwarded to Gemini")
                        
                        elif event == "stop":
                            logger.info(f"Twilio Stream stopped (forwarded {audio_chunks_in} audio chunks)")
                            break
                            
                except Exception as e:
                    logger.error(f"Twilio receiver error: {e}", exc_info=True)

            # ─── Gemini → Twilio (outbound audio) ──────────────────────────
            async def gemini_to_twilio_task():
                nonlocal call_sid
                audio_segments_out = 0
                
                try:
                    async for response in gemini_session.receive():
                        # ── Audio output from model ──
                        if response.server_content and response.server_content.model_turn:
                            for part in response.server_content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    raw_pcm = part.inline_data.data
                                    # Convert 24kHz PCM → 8kHz mu-law → base64
                                    b64_mulaw = gemini_to_twilio(raw_pcm)
                                    # Decode back to raw mu-law for chunking
                                    mulaw_bytes = base64.b64decode(b64_mulaw)
                                    
                                    # Send to Twilio in 160-byte chunks (20ms at 8kHz mu-law)
                                    for i in range(0, len(mulaw_bytes), 160):
                                        chunk = mulaw_bytes[i:i + 160]
                                        payload = base64.b64encode(chunk).decode('ascii')
                                        try:
                                            await websocket.send_json({
                                                "event": "media",
                                                "streamSid": stream_sid,
                                                "media": {"payload": payload}
                                            })
                                        except Exception:
                                            return  # Twilio disconnected
                                    audio_segments_out += 1

                        # ── Tool calls ──
                        if response.tool_call:
                            for fn in response.tool_call.function_calls:
                                name = fn.name
                                args = fn.args
                                logger.info(f"Tool call: {name}({args})")
                                
                                result = await _handle_tool_call(name, args, call_sid)
                                
                                await gemini_session.send(
                                    input=types.LiveClientToolResponse(
                                        function_responses=[
                                            types.FunctionResponse(
                                                name=name,
                                                response=result
                                            )
                                        ]
                                    )
                                )
                        
                        # ── Barge-in (user interrupted) ──
                        if response.server_content and response.server_content.interrupted:
                            logger.info(f"Barge-in: clearing Twilio buffer")
                            try:
                                await websocket.send_json({
                                    "event": "clear",
                                    "streamSid": stream_sid
                                })
                            except Exception:
                                return

                        # ── Turn complete (log) ──
                        if response.server_content and response.server_content.turn_complete:
                            logger.info(f"Turn complete (sent {audio_segments_out} audio segments)")

                except Exception as e:
                    logger.error(f"Gemini receiver error: {e}", exc_info=True)

            # Run both tasks concurrently
            await asyncio.gather(
                twilio_to_gemini_task(),
                gemini_to_twilio_task(),
                return_exceptions=True
            )

    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected.")
    except Exception as e:
        logger.error(f"Media stream error: {e}", exc_info=True)
    finally:
        logger.info(f"Session cleanup for stream={stream_sid}")


async def _handle_tool_call(name: str, args: dict, call_sid: str) -> dict:
    """Process a tool call from Gemini and return the result."""
    result = {"success": False, "message": "Unknown tool"}
    try:
        session = await SessionStore.get_or_create(call_sid, phone_number="ws_call")
        
        if name == "add_order_item":
            menu_item = find_menu_item(args["item_name"])
            if menu_item:
                qty = int(args.get("quantity", 1))
                order_item = OrderItem(
                    menu_item=menu_item,
                    quantity=qty,
                    notes=args.get("notes", "")
                )
                session.add_item(order_item)
                result = {"success": True, "message": f"Added {qty}x {menu_item.name}"}
            else:
                result = {"success": False, "message": f"Item '{args['item_name']}' not found"}
                
        elif name == "remove_order_item":
            if session.remove_item(args["item_name"]):
                result = {"success": True, "message": "Item removed"}
            else:
                result = {"success": False, "message": f"Item '{args['item_name']}' not in order"}
                
        elif name == "finalize_order":
            session.customer_name = args.get("customer_name", "Unknown")
            session.order_type = args.get("order_type", "pickup")
            async with AsyncSessionLocal() as db:
                order_id = await save_order_to_db(session, db)
            result = {"success": True, "message": f"Order #{order_id} finalized"}
    
    except Exception as exc:
        logger.error(f"Tool error '{name}': {exc}")
        result = {"success": False, "message": str(exc)}
    
    return result
