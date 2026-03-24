"""
FastAPI WebSocket endpoint for Twilio Media Streams.
Connects directly to the Google Gemini Multimodal Live API.
"""

import asyncio
import json
import logging
import base64
import audioop
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.menu import get_menu_text, find_menu_item, OrderItem
from app.services.session_store import SessionStore
from app.services.order_service import save_order_to_db

logger = logging.getLogger(__name__)
router = APIRouter()

_genai_client = None

# ── Audio constants ──────────────────────────────────────────────────────────
TWILIO_RATE = 8000
GEMINI_IN_RATE = 16000
GEMINI_OUT_RATE = 24000
SAMPLE_WIDTH = 2       # 16-bit PCM
MULAW_CHUNK = 160      # 20ms of 8kHz mu-law (1 byte/sample)

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
                        "item_name": {"type": "STRING", "description": "Name of menu item"},
                        "quantity": {"type": "INTEGER", "description": "Quantity (e.g., 2)"},
                        "notes": {"type": "STRING", "description": "Special instructions"}
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
                        "item_name": {"type": "STRING", "description": "Name of item to remove"}
                    },
                    "required": ["item_name"]
                }
            },
            {
                "name": "finalize_order",
                "description": "Finalize and submit the order to the kitchen.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "customer_name": {"type": "STRING", "description": "Customer name"},
                        "order_type": {"type": "STRING", "description": "'pickup' or 'delivery'"}
                    },
                    "required": ["customer_name", "order_type"]
                }
            }
        ]
    }
]


class AudioProcessor:
    """Processes 20ms Twilio mu-law chunks incrementally."""
    def __init__(self):
        self._ratecv_state = None
        
    def process_chunk(self, b64_mulaw: str) -> bytes:
        mulaw_bytes = base64.b64decode(b64_mulaw)
        pcm8k = audioop.ulaw2lin(mulaw_bytes, SAMPLE_WIDTH)
        pcm16k, self._ratecv_state = audioop.ratecv(
            pcm8k, SAMPLE_WIDTH, 1,
            TWILIO_RATE, GEMINI_IN_RATE,
            self._ratecv_state
        )
        return pcm16k


def gemini_audio_to_twilio(pcm24k_bytes: bytes) -> list[str]:
    """
    Convert 24kHz PCM16 from Gemini → 8kHz mu-law base64 payloads for Twilio.
    Returns a list of base64-encoded 160-byte mu-law chunks.
    """
    # Resample 24kHz → 8kHz
    pcm8k, _ = audioop.ratecv(pcm24k_bytes, SAMPLE_WIDTH, 1, GEMINI_OUT_RATE, TWILIO_RATE, None)
    # PCM16 → mu-law
    mulaw_bytes = audioop.lin2ulaw(pcm8k, SAMPLE_WIDTH)
    
    # Split into 160-byte chunks (20ms each)
    chunks = []
    for i in range(0, len(mulaw_bytes), MULAW_CHUNK):
        chunk = mulaw_bytes[i:i + MULAW_CHUNK]
        chunks.append(base64.b64encode(chunk).decode('ascii'))
    return chunks


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
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=True
            )
        ),
    )

    try:
        async with client.aio.live.connect(model=MODEL, config=config) as gemini_session:
            logger.info("Connected to Gemini Live API")

            processor = AudioProcessor()

            # ─── Twilio → Gemini ────────────────────────────────────────────
            bot_is_speaking = True  # Starts true because we send a greeting

            async def twilio_to_gemini_task():
                nonlocal stream_sid, call_sid, bot_is_speaking
                chunks_in = 0
                
                # Manual VAD State
                vad_threshold = 800     # RMS threshold for "speaking"
                vad_talk_streak = 0
                vad_silence_streak = 0
                user_is_speaking = False
                activity_started = False  # Tracks if we sent activity_start to Gemini
                
                try:
                    while True:
                        try:
                            message_str = await websocket.receive_text()
                        except WebSocketDisconnect:
                            logger.info("Twilio WS disconnected in receiver")
                            break
                        
                        data = json.loads(message_str)
                        event = data.get("event")
                        
                        if event == "start":
                            stream_sid = data["start"]["streamSid"]
                            call_sid = data["start"]["callSid"]
                            logger.info(f"Stream started: {stream_sid} call={call_sid}")
                            await gemini_session.send(
                                input="Hello! Greet the caller warmly.",
                                end_of_turn=True
                            )
                            logger.info("Sent greeting prompt")
                        
                        elif event == "media":
                            pcm16k = processor.process_chunk(data["media"]["payload"])
                            
                            rms = audioop.rms(pcm16k, 2)
                            if chunks_in % 200 == 0:
                                logger.info(f"Audio In RMS: {rms} (bot_speaking={bot_is_speaking}, user_speaking={user_is_speaking}, activity={activity_started})")
                            
                            if not bot_is_speaking:
                                try:
                                    # Manual VAD: detect speech start/end
                                    if rms >= vad_threshold:
                                        vad_talk_streak += 1
                                        vad_silence_streak = 0
                                        
                                        # Speech detected! Send activity_start if not already sent
                                        if vad_talk_streak > 5 and not activity_started:
                                            logger.info(f"Manual VAD: Speech START (RMS={rms})")
                                            await gemini_session.send_realtime_input(
                                                activity_start=types.ActivityStart()
                                            )
                                            activity_started = True
                                            user_is_speaking = True
                                    else:
                                        vad_silence_streak += 1
                                        
                                        # If user was speaking and now silent for 1s (50 * 20ms)
                                        if user_is_speaking and vad_silence_streak > 50:
                                            logger.info(f"Manual VAD: Speech END (silence={vad_silence_streak} chunks)")
                                            await gemini_session.send_realtime_input(
                                                activity_end=types.ActivityEnd()
                                            )
                                            user_is_speaking = False
                                            activity_started = False
                                            vad_talk_streak = 0
                                            vad_silence_streak = 0
                                            bot_is_speaking = True  # Mute while waiting for response
                                    
                                    # Always send audio to Gemini (it needs audio context)
                                    await gemini_session.send_realtime_input(
                                        audio=types.Blob(
                                            data=pcm16k,
                                            mime_type="audio/pcm;rate=16000"
                                        )
                                    )
                                    
                                except Exception as err:
                                    logger.error(f"Gemini send error: {err}")
                                    break
                                    
                            chunks_in += 1
                        
                        elif event == "stop":
                            logger.info(f"Stream stopped ({chunks_in} chunks received)")
                            break
                            
                except Exception as e:
                    logger.error(f"Twilio receiver error: {e}", exc_info=True)

            # ─── Gemini → Twilio ────────────────────────────────────────────
            async def gemini_to_twilio_task():
                nonlocal call_sid, bot_is_speaking
                audio_out = 0
                
                try:
                    async for response in gemini_session.receive():
                        # ── Audio from model ──
                        if response.server_content and response.server_content.model_turn:
                            if not bot_is_speaking:
                                bot_is_speaking = True  # Mute mic as soon as first audio arrives
                            for part in response.server_content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    payloads = gemini_audio_to_twilio(part.inline_data.data)
                                    for payload in payloads:
                                        try:
                                            await websocket.send_json({
                                                "event": "media",
                                                "streamSid": stream_sid,
                                                "media": {"payload": payload}
                                            })
                                        except Exception:
                                            return
                                    audio_out += 1

                        # ── Tool calls ──
                        if response.tool_call:
                            for fn in response.tool_call.function_calls:
                                logger.info(f"Tool: {fn.name}({fn.args})")
                                result = await _handle_tool_call(fn.name, fn.args, call_sid)
                                await gemini_session.send(
                                    input=types.LiveClientToolResponse(
                                        function_responses=[
                                            types.FunctionResponse(
                                                name=fn.name,
                                                response=result
                                            )
                                        ]
                                    )
                                )
                        
                        # ── Barge-in ──
                        if response.server_content and response.server_content.interrupted:
                            logger.info("Barge-in detected")
                            try:
                                await websocket.send_json({
                                    "event": "clear",
                                    "streamSid": stream_sid
                                })
                            except Exception:
                                return

                        # ── Turn complete ──
                        if response.server_content and response.server_content.turn_complete:
                            bot_is_speaking = False
                            logger.info(f"Turn complete ({audio_out} audio segments sent). Unmuting user.")

                except Exception as e:
                    logger.error(f"Gemini receiver error: {e}", exc_info=True)

            await asyncio.gather(
                twilio_to_gemini_task(),
                gemini_to_twilio_task(),
                return_exceptions=True
            )

    except WebSocketDisconnect:
        logger.info("Twilio WS disconnected.")
    except Exception as e:
        logger.error(f"Media stream error: {e}", exc_info=True)
    finally:
        logger.info(f"Cleanup stream={stream_sid}")


async def _handle_tool_call(name: str, args: dict, call_sid: str) -> dict:
    """Process a Gemini tool call and return the result."""
    result = {"success": False, "message": "Unknown tool"}
    try:
        session = await SessionStore.get_or_create(call_sid, phone_number="ws_call")
        
        if name == "add_order_item":
            menu_item = find_menu_item(args["item_name"])
            if menu_item:
                qty = int(args.get("quantity", 1))
                item = OrderItem(menu_item=menu_item, quantity=qty, notes=args.get("notes", ""))
                session.add_item(item)
                result = {"success": True, "message": f"Added {qty}x {menu_item.name}"}
            else:
                result = {"success": False, "message": f"'{args['item_name']}' not found"}
                
        elif name == "remove_order_item":
            if session.remove_item(args["item_name"]):
                result = {"success": True, "message": "Removed"}
            else:
                result = {"success": False, "message": f"'{args['item_name']}' not in order"}
                
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
