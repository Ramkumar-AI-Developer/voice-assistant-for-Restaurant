"""
LLM orchestration via Groq API (llama-3.3-70b-versatile).

Uses the official Groq Python SDK with AsyncGroq for non-blocking chat
completions with JSON mode.

Two public functions:
  • process_utterance() — extract order actions + generate spoken reply
  • generate_greeting() — one-shot greeting at call start
"""

import json
import logging
import time
import asyncio
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
    return f"""You are Aria, a friendly and efficient voice assistant for Vasantha Vilas restaurant.
Your job is to help callers place food orders over the phone.

RESTAURANT DETAILS (use these when callers ask):
- Name: Vasantha Vilas — Indian Vegetarian Restaurant (Since 2005)
- Address: 306 High Street, Slough SL1 1NB
- Phone: 01753 251030
- Website: https://vasanthavilas.co.uk/
- Opening Hours:
    Monday–Thursday: 10:00 AM – 10:00 PM
    Friday: 10:00 AM – 10:30 PM
    Saturday–Sunday: 9:00 AM – 10:30 PM
- Allergen notice: Nuts, sesame and other allergenic ingredients are used in our kitchen. We cannot guarantee our food is free from traces of allergens.

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


# ── Chat helper ───────────────────────────────────────────────────────────────

async def _chat(
    system_prompt: str,
    messages: list[dict],
    max_tokens: int = 300,
) -> tuple[str, float]:
    """
    Send a chat completion to Groq and return the full response.
    Includes retry with exponential backoff for rate-limit errors.

    Returns (full_text, latency_seconds).
    """
    client = _get_client()
    t0 = time.perf_counter()

    # Build messages list for Groq (OpenAI-compatible format)
    groq_messages = []
    for msg in messages:
        if msg["role"] == "system":
            continue  # handled via system_prompt below
        groq_messages.append({"role": msg["role"], "content": msg["content"]})

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=settings.GROQ_LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *groq_messages,
                ],
                max_tokens=max_tokens,
                temperature=0.3,
                top_p=1.0,
                response_format={"type": "json_object"},
            )

            full_text = response.choices[0].message.content.strip()
            latency = time.perf_counter() - t0
            logger.info(f"Groq LLM [{latency:.2f}s] '{full_text[:100]}'")
            return full_text, latency

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate" in error_str.lower():
                wait_time = (2 ** attempt) + 1
                logger.warning(f"Groq 429 rate limit (attempt {attempt+1}/{max_retries}). Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            else:
                raise

    raise Exception("Groq API rate limit exceeded after all retries")


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
    system_prompt = ""
    filtered_messages = []
    for msg in session_messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        else:
            filtered_messages.append(msg)

    filtered_messages.append({"role": "user", "content": transcript})

    raw, latency = await _chat(system_prompt, filtered_messages, max_tokens=300)

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
        logger.warning(f"Groq returned non-JSON, wrapping as plain reply: {raw[:120]}")
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
    raw, _ = await _chat(system_prompt, messages, max_tokens=80)

    try:
        clean = raw.strip().lstrip("```json").rstrip("```").strip()
        return json.loads(clean).get("reply", raw)
    except Exception:
        return raw if raw else "Welcome to Vasantha Vilas! What can I get for you today?"


async def close() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
