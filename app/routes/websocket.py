"""
FastAPI WebSocket endpoint for Twilio Media Streams.
Connects directly to the Google Gemini Multimodal Live API.
"""

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
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


SYSTEM_INSTRUCTION_TEMPLATE = """
You are Aria, a friendly and efficient voice assistant for "The Golden Fork" restaurant.
Your job is to help callers place food orders over the phone.

MENU:
{menu_text}

STRICT RULES:
- Keep every reply under 35 words. Be brief and warm.
- Say exactly what you mean, in plain language.
- Confirm the caller's items and total. Ask if they want pickup or delivery.
- You are speaking on a live phone call, so be natural and conversational.
- ALWAYS use the provided tools (add_order_item, remove_order_item, finalize_order) to update the system. DO NOT pretend to add items without calling the tool.
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
                "description": "Call this to finalize and submit the order to the kitchen. Use only after confirming the full order, name, and pickup/delivery with the customer.",
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

    # Get the latest menu text and inject it into the prompt
    menu_text = get_menu_text()
    prompt = SYSTEM_INSTRUCTION_TEMPLATE.format(menu_text=menu_text)

    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": {"parts": [{"text": prompt}]},
        "tools": _TOOLS
    }

    try:
        async with client.aio.live.connect(model=MODEL, config=config) as gemini_session:
            logger.info("Connected to Gemini Live API")

            async def twilio_to_gemini_task():
                nonlocal stream_sid
                while True:
                    message_str = await websocket.receive_text()
                    data = json.loads(message_str)
                    
                    event = data.get("event")
                    if event == "start":
                        stream_sid = data["start"]["streamSid"]
                        call_sid = data["start"]["callSid"]
                        logger.info(f"Started Twilio Media Stream: {stream_sid} for call {call_sid}")
                        # Immediately send a greeting text to Gemini to kick off the audio!
                        await gemini_session.send(input="Hello! Please greet the user.", end_of_turn=True)
                    
                    elif event == "media":
                        b64_audio = data["media"]["payload"]
                        pcm16k_chunk = twilio_to_gemini(b64_audio)
                        # Send to Gemini
                        await gemini_session.send_realtime_input(
                            audio=types.Blob(
                                data=pcm16k_chunk,
                                mime_type="audio/pcm;rate=16000"
                            )
                        )
                    
                    elif event == "stop":
                        logger.info("Twilio Stream Stopped")
                        break

            async def gemini_to_twilio_task():
                async for response in gemini_session.receive():
                    if response.server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            # 1. ── Handle Audio Output
                            if part.inline_data:
                                pcm24k_audio = part.inline_data.data
                                b64_mulaw = gemini_to_twilio(pcm24k_audio)
                                await websocket.send_json({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": b64_mulaw}
                                })
                            
                            # 2. ── Handle Function Calls (Tools)
                            elif part.function_call:
                                fn = part.function_call
                                name = fn.name
                                args = fn.args
                                logger.info(f"Gemini Tool Call: {name}({args})")
                                
                                result = {"success": False, "message": "Unknown error"}
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
                                            result = {"success": False, "message": f"Item '{args['item_name']}' not found on menu"}
                                            
                                    elif name == "remove_order_item":
                                        if session.remove_item(args["item_name"]):
                                            result = {"success": True, "message": "Item removed"}
                                        else:
                                            result = {"success": False, "message": f"Item '{args['item_name']}' not currently in order"}
                                            
                                    elif name == "finalize_order":
                                        session.customer_name = args.get("customer_name", "Unknown")
                                        session.order_type = args.get("order_type", "pickup")
                                        async with AsyncSessionLocal() as db:
                                            order_id = await save_order_to_db(session, db)
                                        result = {"success": True, "message": f"Order finalized with ID {order_id}"}
                                
                                except Exception as exc:
                                    logger.error(f"Error handling tool '{name}': {exc}")
                                    result = {"success": False, "message": str(exc)}
                                
                                # Send tool execution result back to Gemini so it understands what happened
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
                    
                    # 3. ── Handle Interruption (Barge-In)
                    if response.server_content and response.server_content.interrupted:
                        logger.info(f"Gemini Interrupted: clearing Twilio buffer for {stream_sid}")
                        await websocket.send_json({
                            "event": "clear",
                            "streamSid": stream_sid
                        })

            # Run both infinitely until disconnection
            await asyncio.gather(
                twilio_to_gemini_task(),
                gemini_to_twilio_task()
            )

    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected normally.")
    except Exception as e:
        logger.error(f"Error in Twilio Media Stream Task: {e}", exc_info=True)
    finally:
        logger.info(f"Cleaned up session for {stream_sid}")
