"""
LLM orchestration via Google Gemini API (gemini-2.5-flash).

Uses the official google-genai Python SDK with streaming for
lower time-to-first-token.

Two public functions:
  • process_utterance() — extract order actions + generate spoken reply (JSON mode)
  • generate_greeting() — one-shot greeting at call start
"""

import json
import logging
import time
from typing import Optional

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


# ── System prompt ─────────────────────────────────────────────────────────────

def build_system_prompt(menu_text: str) -> str:
    return f"""You are Aria, a friendly and efficient voice assistant for "The Golden Fork" restaurant.
Your job is to help callers place food orders over the phone.

STRICT RULES:
- Keep every reply under 35 words — this is voice; brevity is critical.
- Be warm but quick. No filler phrases like "Certainly!" or "Of course!".
- Always confirm the item name and price when adding something to the order.
- If you are unsure what the caller said, ask ONE short clarifying question.
- When the caller is done ordering, ask for their NAME before confirming the order.
- After getting the name, ask if it's for pickup or delivery.
- Then read back the full order with the total and ask for confirmation.
- Do NOT invent items not on the menu. Politely say the item is unavailable.
- Speak naturally — avoid bullet points or markdown in your reply.
- The caller's phone number is automatically captured — do NOT ask for it.

MENU:
{menu_text}

RESPONSE FORMAT — always respond with valid JSON only, no prose outside the JSON:
{{
  "_reasoning": "Quickly analyze the user's intent here before returning actions. Keep it under 2 sentences.",
  "actions": [
    {{"type": "add",    "item_name": "...", "quantity": 1, "notes": ""}},
    {{"type": "remove", "item_name": "..."}},
    {{"type": "set_name", "name": "customer's name"}},
    {{"type": "set_type", "order_type": "pickup or delivery"}},
    {{"type": "confirm"}},
    {{"type": "cancel"}},
    {{"type": "repeat_order"}},
    {{"type": "none"}}
  ],
  "reply": "Your spoken reply to the caller — under 35 words."
}}

You may include multiple actions in one response (e.g. add two items at once).
When the customer tells you their name, include a set_name action.
When they say pickup or delivery, include a set_type action.
"""


# ── Streaming helper ──────────────────────────────────────────────────────────

async def _stream_chat(
    system_prompt: str,
    messages: list[dict],
    max_tokens: int = 300,
) -> tuple[str, float]:
    """
    Stream a chat completion from Gemini and accumulate the full response.
    Streaming gives lower time-to-first-token even though we buffer the result
    before sending to TTS (Twilio requires complete TwiML up front).

    Returns (full_text, latency_seconds).
    """
    client = _get_client()
    t0 = time.perf_counter()

    # Convert messages from OpenAI/Groq format to Gemini format
    contents = []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            continue  # system prompt handled via config
        gemini_role = "user" if role == "user" else "model"
        contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part.from_text(text=msg["content"])],
            )
        )

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.3,
        max_output_tokens=max_tokens,
        top_p=1.0,
        response_mime_type="application/json",
        # Disable "thinking" mode for speed — voice bot needs fast JSON, not deep reasoning
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )

    # Use synchronous streaming run in thread pool to avoid blocking the event loop
    import asyncio

    def _sync_stream():
        parts = []
        for chunk in client.models.generate_content_stream(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=config,
        ):
            try:
                if chunk.text:
                    parts.append(chunk.text)
            except Exception:
                pass  # skip chunks without text (e.g. thinking chunks)
        return "".join(parts)

    full_text = await asyncio.get_event_loop().run_in_executor(None, _sync_stream)
    full_text = full_text.strip()

    latency = time.perf_counter() - t0
    logger.info(f"Gemini [{latency:.2f}s] '{full_text[:100]}'")
    return full_text, latency


# ── Public API ────────────────────────────────────────────────────────────────

async def process_utterance(
    session_messages: list[dict],
    transcript: str,
) -> dict:
    """
    Given conversation history + new user transcript, return:
    {
        "actions": [...],
        "reply":   "spoken reply",
        "latency": float
    }
    """
    # Extract system prompt from session messages
    system_prompt = ""
    filtered_messages = []
    for msg in session_messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        else:
            filtered_messages.append(msg)

    # Add the new user message
    filtered_messages.append({"role": "user", "content": transcript})

    raw, latency = await _stream_chat(system_prompt, filtered_messages, max_tokens=300)

    # Strip accidental markdown fences
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
        clean = clean.strip()

    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        logger.warning(f"Gemini returned non-JSON, wrapping as plain reply: {raw[:120]}")
        parsed = {
            "actions": [{"type": "none"}],
            "reply": raw[:200],
        }

    parsed["latency"] = latency
    return parsed


async def generate_greeting(menu_text: str) -> str:
    """Generate a warm, personalised greeting at the start of the call."""
    system_prompt = build_system_prompt(menu_text)
    messages = [
        {"role": "user", "content": "SYSTEM_EVENT: Call just connected. Greet the caller warmly and ask what they would like to order."},
    ]
    raw, _ = await _stream_chat(system_prompt, messages, max_tokens=80)

    # Try to parse JSON reply field; fall back to raw text
    try:
        clean = raw.strip().lstrip("```json").rstrip("```").strip()
        return json.loads(clean).get("reply", raw)
    except Exception:
        return raw if raw else "Welcome to The Golden Fork! What can I get for you today?"


async def close() -> None:
    global _client
    if _client is not None:
        _client = None
