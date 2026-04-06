"""
WebSocket handler: Twilio Media Stream ←→ OpenAI Realtime API bridge.

Architecture:
  Caller ↔ Twilio (g711_ulaw) ↔ /media-stream ↔ OpenAI Realtime API (g711_ulaw)

Features:
  • Native g711_ulaw — zero audio resampling
  • Server-side VAD with barge-in support
  • Function calling tools for order tracking → DB + WhatsApp + SMS
  • Real-time dashboard event push
"""

import json
import asyncio
import logging
import base64
import time

import httpx
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.models.menu import get_menu_text, find_menu_item, OrderItem
from app.models.session import CallSession, CallStage
from app.services.session_store import SessionStore
from app.database import AsyncSessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)

# OpenAI Realtime API endpoint
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"

# ── Dashboard event bus (connected frontends) ─────────────────────────────────
dashboard_clients: set[WebSocket] = set()


async def broadcast_dashboard_event(event_type: str, data: dict):
    """Push a real-time event to all connected dashboard WebSocket clients."""
    message = json.dumps({"type": event_type, "data": data})
    disconnected = set()
    for client in dashboard_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)
    dashboard_clients.difference_update(disconnected)


# ── Tool definitions for OpenAI ───────────────────────────────────────────────
ORDER_TOOLS = [
    {
        "type": "function",
        "name": "add_to_order",
        "description": "Add a menu item to the customer's order. Call this when the customer wants to order something.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string", "description": "Name of the menu item to add"},
                "quantity": {"type": "integer", "description": "Number of items to add, default 1"},
                "notes": {"type": "string", "description": "Special instructions or customizations"},
            },
            "required": ["item_name"],
        },
    },
    {
        "type": "function",
        "name": "remove_from_order",
        "description": "Remove an item from the customer's current order.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string", "description": "Name of the item to remove"},
            },
            "required": ["item_name"],
        },
    },
    {
        "type": "function",
        "name": "get_order_summary",
        "description": "Get the current order summary with all items and total. Call this when the customer asks what's in their order or wants to review.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "set_customer_info",
        "description": "Set the customer's name. Call this when the customer provides their name.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Customer's name"},
            },
        },
    },
    {
        "type": "function",
        "name": "confirm_order",
        "description": "Finalize and confirm the customer's order. Call this ONLY when the customer explicitly confirms. This saves the order and notifies the kitchen.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "cancel_order",
        "description": "Cancel the entire order and end the call. You MUST call this whenever the customer says they don't want to order, changes their mind and wants to leave, or says goodbye without ordering.",
        "parameters": {"type": "object", "properties": {}},
    },
]

SYSTEM_MESSAGE = """You are Aria, an exceptionally polite, warm, and charming voice assistant for Vasantha Vilas restaurant.
Your job is to help callers place food orders over the phone with the utmost courtesy and genuine warmth.

RESTAURANT DETAILS (FIXED — never invent different addresses):
- Name: Vasantha Vilas — Indian Vegetarian Restaurant (Since 2005)
- Address: 306 High Street, Slough SL1 1NB
- IMPORTANT: The ONLY address is 306 High Street, Slough SL1 1NB. Do NOT make up or guess any other address. If asked about location, always say exactly: "We're at 306 High Street, Slough, S L 1, 1 N B — lovely and easy to find!"
- Email: hello@vasanthavilas.co.uk
- Phone: 01252 438046
- Website: https://vasanthavilas.co.uk/
- Opening Hours:
    Monday–Thursday: 10:00 AM – 10:00 PM
    Friday: 10:00 AM – 10:30 PM
    Saturday–Sunday: 9:00 AM – 10:30 PM
- Allergen notice: Nuts, sesame and other allergenic ingredients are used in our kitchen.

ABOUT THE RESTAURANT:
Since 2005, Vasantha Vilas has been a cornerstone of the culinary scene, delighting customers with authentic South Indian vegetarian cuisine. We proudly pioneered the introduction of authentic South Indian flavours to London. Under the leadership of Mr. Kannan Murugan and Mr. Mohamed Thasleem, we combine modern elegance with timeless South Indian culinary heritage.

CRITICAL RULES:
1. LANGUAGE:
   - Your VERY FIRST message must ALWAYS be in English. Never start in any other language.
   - If the caller speaks Hindi or switches to Hindi, you MUST continue the ENTIRE rest of the conversation in Hindi. Do not switch back to English unless the caller does. Keep taking the order, confirming, and saying goodbye all in Hindi.
   - If speaking English, use a natural, warm British tone. Be genuinely courteous, polite, and conversational.

2. POLITENESS & UK SLANG (VERY IMPORTANT):
   - You MUST be extremely polite at all times. Treat every caller like a valued guest.
   - Use authentic British expressions naturally throughout the conversation:
     • "Lovely", "brilliant", "smashing", "cracking choice", "wonderful"
     • "No worries at all", "absolutely", "of course", "certainly"
     • "Cheers", "ta", "sorted", "right you are"
     • "That's a proper good choice", "you've got great taste"
     • "Not a problem", "happy to help", "my pleasure"
   - Always say "please" and "thank you" generously.
   - When someone orders, respond with warmth: "Oh lovely, great choice!", "Brilliant, that's one of our favourites!", "Smashing, I'll pop that on for you."
   - If the caller says thank you, always respond warmly: "You're very welcome!", "My pleasure!", "Not at all, happy to help!"
   - If the caller apologises, be reassuring: "No need to apologise at all!", "Don't worry about it one bit!", "That's absolutely fine!"
   - Use "sorry" politely when needed: "So sorry about that", "Apologies, let me sort that out for you"

3. VOICE & TONE:
   - Act exactly like a real human. Do NOT sound robotic, scripted, or overly formal.
   - Use natural conversational fillers appropriately (e.g., "umm", "let me see", "ah", "hmm").
   - Mimic slight pauses as if you are typing or looking at a menu ("let me just pop that in...", "bear with me a second").
   - Speak like a genuinely kind, warm British person on the phone.
   - Sound like you're smiling — be cheerful, patient, and never rushed.
   - Keep every reply VERY SHORT — 1-2 sentences max. This is a phone call, not a lecture.
   - Make the caller feel welcomed, valued, and looked after.

4. SILENCE & NOISE HANDLING (VERY IMPORTANT):
   - If you hear silence, "mmm", "hmm", background noise, static, or any unclear sound:
     → Do NOT interpret it as an order or a cancellation.
     → Do NOT remove items from the order.
     → Do NOT call any tools.
     → Simply say "Hello, are you still there, love?" or "So sorry, I didn't quite catch that — could you say that again for me, please?"
   - NEVER clear or modify the order based on unclear audio.

5. ORDER FLOW:
   - When adding items, say something warm like "Lovely, I'll pop that on for you now" or "Brilliant, adding that right away" while calling add_to_order.
   - Use get_order_summary to read back the order when asked.
   - When done ordering, politely ask for their name: "Could I take your name, please?" then use set_customer_info. If unsure, say "So sorry, could you spell that out for me, please?"
   - Read back the full order, then ask for confirmation: "Just to make sure I've got everything right for you..."
   - When confirmed, use confirm_order and give a warm, polite goodbye: "Brilliant, that's all sorted! Your total comes to £X. We'll have that ready for you shortly. Thank you ever so much for calling Vasantha Vilas — we really appreciate it. Cheers, have a lovely day!"
   - If the customer decides NOT to order anything, or just says goodbye without ordering, you MUST use the `cancel_order` tool so the phone line can be disconnected.
   - The phone number is captured automatically — do NOT ask for it.

6. FAREWELL POLITENESS:
   - Always end calls with genuine warmth and appreciation.
   - Use phrases like: "Thank you ever so much", "We really appreciate your custom", "Have a wonderful day", "Lovely speaking with you", "Take care now", "Cheers!"
   - Make the caller feel valued and eager to call back.

MENU:
{menu}
"""


# ── Tool execution ────────────────────────────────────────────────────────────

async def execute_tool(name: str, args: dict, session: CallSession) -> str:
    """Execute a function call and return the result as a string."""
    
    if name == "add_to_order":
        item_name = args.get("item_name", "")
        quantity = max(1, int(args.get("quantity", 1)))
        notes = args.get("notes", "")
        
        menu_item = find_menu_item(item_name)
        if menu_item:
            session.add_item(OrderItem(menu_item=menu_item, quantity=quantity, notes=notes))
            session.stage = CallStage.TAKING_ORDER
            logger.info(f"[{session.call_sid}] +{quantity}× {menu_item.name}")
            
            await broadcast_dashboard_event("order_update", {
                "call_sid": session.call_sid,
                "action": "add",
                "item": menu_item.name,
                "quantity": quantity,
                "total": session.order_total,
            })
            
            return json.dumps({
                "success": True,
                "message": f"Added {quantity}x {menu_item.name} (£{menu_item.price:.2f} each) to the order. Current total: £{session.order_total:.2f}",
            })
        else:
            return json.dumps({
                "success": False,
                "message": f"'{item_name}' was not found on the menu. Please suggest a similar available item.",
            })
    
    elif name == "remove_from_order":
        item_name = args.get("item_name", "")
        removed = session.remove_item(item_name)
        if removed:
            logger.info(f"[{session.call_sid}] Removed '{item_name}'")
            return json.dumps({"success": True, "message": f"Removed {item_name}. Current total: £{session.order_total:.2f}"})
        else:
            return json.dumps({"success": False, "message": f"'{item_name}' was not found in the current order."})
    
    elif name == "get_order_summary":
        if not session.order_items:
            return json.dumps({"summary": "The order is currently empty.", "total": 0})
        items = [f"{oi.quantity}x {oi.menu_item.name} (£{oi.subtotal:.2f})" for oi in session.order_items]
        return json.dumps({
            "items": items,
            "total": session.order_total,
            "customer_name": session.customer_name or "Not set",
        })
    
    elif name == "set_customer_info":
        name_val = args.get("name", "")
        
        result_parts = []
        if name_val:
            session.customer_name = name_val
            result_parts.append(f"Customer name set to {name_val}")
        
        logger.info(f"[{session.call_sid}] Customer info: name={session.customer_name}")
        return json.dumps({"success": True, "message": ". ".join(result_parts) if result_parts else "No changes made"})
    
    elif name == "confirm_order":
        if not session.order_items:
            return json.dumps({"success": False, "message": "Cannot confirm — order is empty."})
        
        session.stage = CallStage.COMPLETED
        logger.info(f"[{session.call_sid}] Order confirmed — £{session.order_total:.2f}")
        
        # Save to database + send WhatsApp + SMS
        try:
            from app.services.order_service import save_order_to_db
            async with AsyncSessionLocal() as db:
                order_id = await save_order_to_db(session, db)
                logger.info(f"[{session.call_sid}] Order #{order_id} saved, WhatsApp sent")
        except Exception as exc:
            logger.error(f"[{session.call_sid}] DB/WhatsApp error: {exc}", exc_info=True)
        
        await broadcast_dashboard_event("new_order", {
            "call_sid": session.call_sid,
            "customer_name": session.customer_name,
            "total": session.order_total,
            "items_count": len(session.order_items),
        })
        
        return json.dumps({
            "success": True,
            "message": f"Order confirmed! Total: £{session.order_total:.2f}. The kitchen has been notified. Thank the customer politely and say goodbye.",
        })
    
    elif name == "cancel_order":
        session.stage = CallStage.COMPLETED
        logger.info(f"[{session.call_sid}] Order cancelled by customer")
        
        await broadcast_dashboard_event("order_cancelled", {
            "call_sid": session.call_sid,
        })
        
        return json.dumps({
            "success": True,
            "message": "Order has been cancelled completely. Please apologize politely and say a warm goodbye.",
        })
    
    return json.dumps({"error": f"Unknown tool: {name}"})


# ── WebSocket handler ─────────────────────────────────────────────────────────

@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket, call_sid: str = None):
    """Bridge Twilio's bidirectional audio stream with OpenAI's Realtime API."""
    await websocket.accept()
    logger.info(f"Twilio WebSocket connected on /media-stream (query call_sid={call_sid})")

    stream_sid = None
    session = None
    order_confirmed = False
    order_cancelled = False
    shutdown_event = asyncio.Event()  # Signal both loops to stop
    
    # Pre-fetch session if call_sid was provided in the URL
    if call_sid:
        session = await SessionStore.get(call_sid)
        if session and session.customer_name:
            logger.info(f"[{call_sid}] Pre-fetched session for returning customer: {session.customer_name}")

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

            # ── Configure session with tools ──────────────────────────────
            menu_text = get_menu_text()
            
            instructions = SYSTEM_MESSAGE.format(menu=menu_text)

            session_config = {
                "type": "session.update",
                "session": {
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.9,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 1200,
                    },
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "voice": "shimmer",
                    "instructions": instructions,
                    "modalities": ["text", "audio"],
                    "temperature": 0.6,
                    "max_response_output_tokens": 500,
                    "tools": ORDER_TOOLS,
                    "tool_choice": "auto",
                    "input_audio_transcription": {
                        "model": "whisper-1",
                    },
                }
            }
            await openai_ws.send(json.dumps(session_config))
            logger.info("Sent session config with tools to OpenAI")

            # Note: We NO LONGER send the initial greeting here. We wait for Twilio's "start" event below.
            logger.info("Sent session config with tools to OpenAI")

            # ── Twilio → OpenAI ───────────────────────────────────────────
            async def twilio_to_openai():
                nonlocal stream_sid, call_sid, session
                try:
                    async for message in websocket.iter_text():
                        if shutdown_event.is_set():
                            break
                        data = json.loads(message)
                        event = data.get("event")

                        if event == "start":
                            stream_sid = data["start"]["streamSid"]
                            tw_call_sid = data["start"]["callSid"]
                            if not call_sid:
                                call_sid = tw_call_sid
                                
                            logger.info(f"Stream started: {stream_sid} call={call_sid}")
                            
                            # Get session created by call.py (has correct phone number)
                            if not session:
                                session = await SessionStore.get(call_sid)
                                if not session:
                                    # Fallback — extract phone from Twilio start event if available
                                    custom_params = data["start"].get("customParameters", {})
                                    phone = custom_params.get("callerPhone", "unknown")
                                    session = await SessionStore.create(call_sid, phone_number=phone)
                            
                            await broadcast_dashboard_event("call_started", {
                                "call_sid": call_sid,
                                "stream_sid": stream_sid,
                            })
                            
                            # Trigger greeting ONLY AFTER Twilio stream is ready
                            # Use UK timezone for time-appropriate greeting
                            from datetime import datetime, timezone, timedelta
                            uk_now = datetime.now(timezone.utc)
                            # Approximate BST: UTC+1 from last Sunday of March to last Sunday of October
                            uk_month = uk_now.month
                            if 4 <= uk_month <= 10:  # BST (approximate)
                                uk_hour = (uk_now.hour + 1) % 24
                            else:  # GMT
                                uk_hour = uk_now.hour
                            
                            if uk_hour < 12:
                                time_greeting = "Good morning"
                            elif uk_hour < 17:
                                time_greeting = "Good afternoon"
                            else:
                                time_greeting = "Good evening"
                            
                            # Build a warm, polite UK-style greeting based on time of day
                            if uk_hour < 12:
                                greeting_text = (
                                    f"{time_greeting}! Thank you ever so much for calling Vasantha Vilas. "
                                    f"How lovely to hear from you — what can I get for you today?"
                                )
                            elif uk_hour < 17:
                                greeting_text = (
                                    f"{time_greeting}! Thanks ever so much for ringing Vasantha Vilas. "
                                    f"Lovely to have you on the line — what can I help you with today?"
                                )
                            else:
                                greeting_text = (
                                    f"{time_greeting}! Thank you so much for calling Vasantha Vilas. "
                                    f"How wonderful to hear from you — what can I get for you this evening?"
                                )
                            
                            await openai_ws.send(json.dumps({
                                "type": "response.create",
                                "response": {
                                    "modalities": ["text", "audio"],
                                    "instructions": f"Say exactly: '{greeting_text}' — keep it extremely gentle, polite, and warmly hospitable. Speak with a soothing British accent and sound like you're smiling.",
                                }
                            }))

                        elif event == "media":
                            await openai_ws.send(json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": data["media"]["payload"],
                            }))

                        elif event == "stop":
                            logger.info("Twilio stream stopped")
                            break

                except WebSocketDisconnect:
                    logger.info("Twilio WebSocket disconnected")
                except websockets.exceptions.ConnectionClosed:
                    logger.info("OpenAI connection closed during send")
                except Exception as e:
                    logger.error(f"Twilio→OpenAI error: {e}")

            # ── OpenAI → Twilio ───────────────────────────────────────────
            async def openai_to_twilio():
                nonlocal stream_sid, session, order_confirmed, order_cancelled
                audio_chunks_sent = 0
                turn_count = 0
                conversation_item_ids: list[str] = []  # Track item IDs for truncation
                
                # Track pending function calls
                pending_fn_calls: dict[str, dict] = {}  # call_id → {name, args_buffer}
                
                try:
                    async for message in openai_ws:
                        response = json.loads(message)
                        event_type = response.get("type", "")

                        # ── Audio response ────────────────────────────
                        if event_type == "response.audio.delta" and stream_sid:
                            audio_payload = response.get("delta", "")
                            if audio_payload:
                                await websocket.send_json({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": audio_payload},
                                })
                                audio_chunks_sent += 1

                        # ── User interruption (barge-in) ──────────────
                        elif event_type == "input_audio_buffer.speech_started":
                            logger.info("User interruption — clearing buffer and cancelling generation")
                            if stream_sid:
                                await websocket.send_json({
                                    "event": "clear",
                                    "streamSid": stream_sid,
                                })
                                # Tell OpenAI to stop generating audio for the current response
                                await openai_ws.send(json.dumps({"type": "response.cancel"}))
                            audio_chunks_sent = 0

                        # ── Audio done ────────────────────────────────
                        elif event_type == "response.audio.done":
                            logger.info(f"Audio done ({audio_chunks_sent} chunks)")
                            audio_chunks_sent = 0
                            
                            # Auto-hangup after order confirmation or cancellation goodbye
                            if order_confirmed or order_cancelled:
                                logger.info("Call finished/cancelled + goodbye spoken — hanging up in 4s")
                                await asyncio.sleep(4)
                                shutdown_event.set()
                                # Use Twilio REST API to terminate the actual phone call
                                if call_sid:
                                    try:
                                        async with httpx.AsyncClient() as client:
                                            await client.post(
                                                f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Calls/{call_sid}.json",
                                                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                                                data={"Status": "completed"},
                                            )
                                        logger.info(f"[{call_sid}] Twilio call terminated via REST API")
                                    except Exception as e:
                                        logger.warning(f"[{call_sid}] Failed to terminate call via API: {e}")
                                # Also close the WebSocket stream
                                try:
                                    await websocket.close()
                                except Exception:
                                    pass
                                return  # Exit the loop

                        # ── Function call started ─────────────────────
                        elif event_type == "response.output_item.added":
                            item = response.get("item", {})
                            if item.get("type") == "function_call":
                                call_id = item.get("call_id", "")
                                fn_name = item.get("name", "")
                                pending_fn_calls[call_id] = {"name": fn_name, "args_buffer": ""}
                                logger.info(f"Function call started: {fn_name} (id={call_id})")

                        # ── Function call args streaming ──────────────
                        elif event_type == "response.function_call_arguments.delta":
                            call_id = response.get("call_id", "")
                            if call_id in pending_fn_calls:
                                pending_fn_calls[call_id]["args_buffer"] += response.get("delta", "")

                        # ── Function call complete → execute ──────────
                        elif event_type == "response.function_call_arguments.done":
                            call_id = response.get("call_id", "")
                            fn_info = pending_fn_calls.pop(call_id, None)
                            
                            if fn_info and session:
                                fn_name = fn_info["name"]
                                try:
                                    fn_args = json.loads(response.get("arguments", "{}"))
                                except json.JSONDecodeError:
                                    fn_args = {}
                                
                                logger.info(f"Executing tool: {fn_name}({fn_args})")
                                result = await execute_tool(fn_name, fn_args, session)
                                logger.info(f"Tool result: {result[:100]}")
                                
                                # Track if order was confirmed or cancelled
                                if fn_name == "confirm_order" and '"success": true' in result.lower():
                                    order_confirmed = True
                                elif fn_name == "cancel_order" and '"success": true' in result.lower():
                                    order_cancelled = True
                                
                                # Send function output back to OpenAI
                                await openai_ws.send(json.dumps({
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                        "call_id": call_id,
                                        "output": result,
                                    }
                                }))
                                
                                # Trigger OpenAI to respond with audio
                                await openai_ws.send(json.dumps({
                                    "type": "response.create",
                                }))

                        # ── Transcripts ───────────────────────────────
                        elif event_type == "response.audio_transcript.done":
                            transcript = response.get("transcript", "")
                            logger.info(f"🤖 Assistant: {transcript[:120]}")
                            if session:
                                session.add_message("assistant", transcript)

                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            transcript = response.get("transcript", "")
                            item_id = response.get("item_id", "")
                            logger.info(f"👤 User: {transcript[:120]}")
                            if item_id:
                                conversation_item_ids.append(item_id)
                            if session:
                                session.add_message("user", transcript)

                        # ── Session events ────────────────────────────
                        elif event_type == "session.created":
                            logger.info("OpenAI session created")
                        elif event_type == "session.updated":
                            logger.info("OpenAI session configured")

                        elif event_type == "response.done":
                            usage = response.get("response", {}).get("usage", {})
                            if usage:
                                logger.info(f"Tokens: in={usage.get('input_tokens', 0)} out={usage.get('output_tokens', 0)}")
                            
                            # Track conversation turns and truncate old ones to prevent context overflow
                            turn_count += 1
                            # Collect output item IDs
                            for item in response.get("response", {}).get("output", []):
                                item_id = item.get("id")
                                if item_id:
                                    conversation_item_ids.append(item_id)
                            
                            # After 10 turns, prune old items to keep context lean
                            MAX_CONTEXT_ITEMS = 20  # Keep last 20 conversation items
                            if len(conversation_item_ids) > MAX_CONTEXT_ITEMS:
                                items_to_remove = conversation_item_ids[:-MAX_CONTEXT_ITEMS]
                                for old_id in items_to_remove:
                                    try:
                                        await openai_ws.send(json.dumps({
                                            "type": "conversation.item.delete",
                                            "item_id": old_id,
                                        }))
                                    except Exception:
                                        pass
                                conversation_item_ids = conversation_item_ids[-MAX_CONTEXT_ITEMS:]
                                logger.info(f"Pruned {len(items_to_remove)} old conversation items (turn {turn_count})")
                                
                                # Inject current order state so AI remembers what's been ordered
                                if session and session.order_items:
                                    items_list = ", ".join(
                                        f"{oi.quantity}x {oi.menu_item.name}" for oi in session.order_items
                                    )
                                    state_summary = (
                                        f"[SYSTEM CONTEXT REMINDER] "
                                        f"Current order so far: {items_list}. "
                                        f"Total: £{session.order_total:.2f}. "
                                        f"Customer name: {session.customer_name or 'not yet provided'}. "
                                        f"Do NOT ask for items already in the order again."
                                    )
                                    await openai_ws.send(json.dumps({
                                        "type": "conversation.item.create",
                                        "item": {
                                            "type": "message",
                                            "role": "user",
                                            "content": [{
                                                "type": "input_text",
                                                "text": state_summary,
                                            }],
                                        }
                                    }))
                                    logger.info(f"Injected order state reminder: {items_list}")

                        # ── Errors ────────────────────────────────────
                        elif event_type == "error":
                            error_info = response.get("error", {})
                            error_message = error_info.get("message", str(response))
                            if "Cancellation failed" in error_message or "no active response found" in error_message:
                                # Harmless error caused by natural barge-in timing
                                pass
                            else:
                                logger.error(f"OpenAI error: {error_message}")

                except WebSocketDisconnect:
                    logger.info("Twilio WebSocket disconnected (caller hung up)")
                    shutdown_event.set()
                except websockets.exceptions.ConnectionClosed:
                    logger.info("OpenAI WebSocket closed")
                except Exception as e:
                    logger.error(f"OpenAI→Twilio error: {e}", exc_info=False)

            # ── Run both directions concurrently ──────────────────────────
            await asyncio.gather(twilio_to_openai(), openai_to_twilio())

    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"Failed to connect to OpenAI Realtime API: {e}")
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}", exc_info=True)
    finally:
        # Save call log on disconnect
        if session and call_sid:
            try:
                from app.services.order_service import save_call_log
                async with AsyncSessionLocal() as db:
                    await save_call_log(session, db)
            except Exception as exc:
                logger.error(f"Failed to save call log: {exc}")
            
            await broadcast_dashboard_event("call_ended", {
                "call_sid": call_sid,
                "duration": int(time.monotonic() - session.created_at),
                "stage": session.stage.value,
            })
        
        logger.info(f"Media stream session ended (call={call_sid})")


# ── Dashboard WebSocket endpoint ──────────────────────────────────────────────

@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await websocket.accept()
    dashboard_clients.add(websocket)
    logger.info(f"Dashboard client connected ({len(dashboard_clients)} total)")
    
    try:
        # Keep alive — wait for disconnect
        while True:
            try:
                # Receive pings or messages from frontend
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        dashboard_clients.discard(websocket)
        logger.info(f"Dashboard client disconnected ({len(dashboard_clients)} total)")
