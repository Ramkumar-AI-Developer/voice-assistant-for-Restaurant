"""
LLM orchestration via Groq SDK (llama-3.3-70b-versatile).

Uses the official groq Python SDK — AsyncGroq for all async paths,
with streaming enabled for lower time-to-first-token.

Two public functions:
  • process_utterance() — extract order actions + generate spoken reply (JSON mode)
  • generate_greeting() — one-shot greeting at call start
"""

import json
import logging
import time
from typing import Optional

from groq import AsyncGroq

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncGroq] = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
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

async def _stream_chat(messages: list[dict], max_tokens: int = 300) -> tuple[str, float]:
    """
    Stream a chat completion from Groq and accumulate the full response.
    Streaming gives lower time-to-first-token even though we buffer the result
    before sending to TTS (Twilio requires complete TwiML up front).

    Returns (full_text, latency_seconds).
    """
    client = _get_client()
    t0 = time.perf_counter()
    chunks: list[str] = []

    stream = await client.chat.completions.create(
        model=settings.GROQ_LLM_MODEL,          # llama-3.3-70b-versatile
        messages=messages,
        temperature=0.3,                         # low temperature = fast + deterministic
        max_completion_tokens=max_tokens,
        top_p=1,
        stream=True,
        stop=None,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            chunks.append(delta)

    latency = time.perf_counter() - t0
    full_text = "".join(chunks).strip()
    logger.info(f"LLM [{latency:.2f}s] '{full_text[:100]}'")
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
    messages = session_messages + [{"role": "user", "content": transcript}]

    raw, latency = await _stream_chat(messages, max_tokens=300)

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
        logger.warning(f"LLM returned non-JSON, wrapping as plain reply: {raw[:120]}")
        parsed = {
            "actions": [{"type": "none"}],
            "reply": raw[:200],
        }

    parsed["latency"] = latency
    return parsed


async def generate_greeting(menu_text: str) -> str:
    """Generate a warm, personalised greeting at the start of the call."""
    system = build_system_prompt(menu_text)
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": "SYSTEM_EVENT: Call just connected. Greet the caller warmly and ask what they would like to order."},
    ]
    raw, _ = await _stream_chat(messages, max_tokens=80)

    # Try to parse JSON reply field; fall back to raw text
    try:
        clean = raw.strip().lstrip("```json").rstrip("```").strip()
        return json.loads(clean).get("reply", raw)
    except Exception:
        return raw if raw else "Welcome to The Golden Fork! What can I get for you today?"


async def close() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
