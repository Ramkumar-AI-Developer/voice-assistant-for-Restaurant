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
import time

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
]

SYSTEM_MESSAGE = """You are Aria, an elegant, polite, and gentle voice assistant for Vasantha Vilas restaurant.
Your job is to help callers place food orders over the phone.

RESTAURANT DETAILS:
- Name: Vasantha Vilas — Indian Vegetarian Restaurant (Since 2005)
- Address: 306 High Street, Slough SL1 1NB (Only for Slough location)
- Email: hello@vasanthavilas.co.uk
- Phone: 01753 251030
- Website: https://vasanthavilas.co.uk/
- Opening Hours:
    Monday–Thursday: 10:00 AM – 10:00 PM
    Friday: 10:00 AM – 10:30 PM
    Saturday–Sunday: 9:00 AM – 10:30 PM
- Allergen notice: Nuts, sesame and other allergenic ingredients are used in our kitchen. We cannot guarantee our food is free from traces of allergens.

ABOUT THE RESTAURANT:
Your gateway to the exquisite world of Authentic Indian Vegetarian Cuisine.
Since 2005, Vasantha Vilas has been a cornerstone of East Ham’s culinary scene, delighting customers with the finest vegetarian cuisine. Formerly known as Vasanta Vilas, we proudly pioneered the introduction of authentic South Indian flavors to London.
Our unwavering commitment to quality and flavor has made us a cherished destination for visitors from Leicester, Manchester, and Birmingham. At Vasantha Vilas, guests are drawn by the irresistible aroma and the heartfelt warmth of our hospitality.
Under the visionary leadership of Mr. Kannan Murugan and Mr. Mohamed Thasleem, we’ve embarked on an exciting journey to redefine the dining experience. Vasantha Vilas now combines modern elegance with the timeless essence of South Indian culinary heritage.

RULES:
- When the call starts, your VERY FIRST MESSAGE must ALWAYS be in English. Never start in Spanish. After the greeting, you can freely switch to Hindi if the caller speaks Hindi.
- Keep every reply short and natural — this is a phone call, not a chat.
- If you hear silence, background static, or unclear noise, DO NOT guess or hallucinate an order. Simply say "Hello, are you still there?"
- If speaking English, use a British (UK) accent. Be casual, conversational, and human-like. Use filler words (like "hmm", "let me see", "yeah", "accha", "thik hai").
- When asked to add an item, you can quickly say "Got it, adding that now" while you trigger the add_to_order tool, so there is no awkward silence.
- Use get_order_summary to read back the order when asked.
- When the caller is done ordering, politely ask for their NAME for the order, then use set_customer_info. ONLY set the name if you clearly heard it. If unsurse, ask them to repeat or spell it. 
- Then read back the full order and ask for final confirmation.
- When they confirm, use confirm_order to finalize, and immediately say your goodbye thank you message.
- The caller's phone number is automatically captured — do NOT ask for it.

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
                        "threshold": 0.8,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 1000,
                    },
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "voice": "coral",
                    "instructions": instructions,
                    "modalities": ["text", "audio"],
                    "temperature": 0.8,
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
                            await openai_ws.send(json.dumps({
                                "type": "response.create",
                                "response": {
                                    "modalities": ["text", "audio"],
                                    "instructions": "Greet the caller warmly and ask what they would like to order today. Keep it under 20 words.",
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
                nonlocal stream_sid, session, order_confirmed
                audio_chunks_sent = 0
                
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
                            logger.info("User interruption — clearing buffer")
                            if stream_sid:
                                await websocket.send_json({
                                    "event": "clear",
                                    "streamSid": stream_sid,
                                })
                            audio_chunks_sent = 0

                        # ── Audio done ────────────────────────────────
                        elif event_type == "response.audio.done":
                            logger.info(f"Audio done ({audio_chunks_sent} chunks)")
                            audio_chunks_sent = 0
                            
                            # Auto-hangup after order confirmation goodbye
                            if order_confirmed:
                                logger.info("Order confirmed + goodbye spoken — hanging up in 7s")
                                await asyncio.sleep(7)
                                shutdown_event.set()
                                # Close Twilio WebSocket to end the call
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
                                
                                # Track if order was confirmed
                                if fn_name == "confirm_order" and '"success": true' in result.lower():
                                    order_confirmed = True
                                
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
                            logger.info(f"👤 User: {transcript[:120]}")
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

                        # ── Errors ────────────────────────────────────
                        elif event_type == "error":
                            error_info = response.get("error", {})
                            logger.error(f"OpenAI error: {error_info.get('message', response)}")

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
                "duration": int(time.time() - session.created_at),
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
