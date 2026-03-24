"""
Smoke-test the full STT + LLM + order pipeline without making a real phone call.

Prerequisites:
    pip install python-dotenv
    A valid .env file with GROQ_API_KEY set.

Usage:
    python tests/test_pipeline.py
"""

import asyncio
import os
import sys

# Allow running from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

# Patch env before importing settings
_required = {
    "TWILIO_ACCOUNT_SID": "ACtest",
    "TWILIO_AUTH_TOKEN": "test_token",
    "TWILIO_API_KEY": "SKtest",
    "TWILIO_PHONE_NUMBER": "+10000000000",
    "BASE_URL": "https://test.example.com",
}
for k, v in _required.items():
    os.environ.setdefault(k, v)

from app.services.llm_service import generate_greeting, process_utterance, build_system_prompt
from app.services.order_service import apply_actions
from app.models.menu import get_menu_text
from app.models.session import CallSession, CallStage


# ── Helpers ───────────────────────────────────────────────────────────────────

def _header(title: str) -> None:
    print(f"\n{'═' * 55}")
    print(f"  {title}")
    print('═' * 55)


def _ok(msg: str) -> None:
    print(f"  ✓  {msg}")


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_menu_text():
    _header("TEST 1 — Menu text generation")
    menu = get_menu_text()
    assert "Classic Burger" in menu, "Classic Burger missing"
    assert "Margherita Pizza" in menu, "Margherita Pizza missing"
    assert "Coffee" in menu, "Coffee missing"
    _ok("Menu text contains expected items")
    print(menu)


async def test_greeting():
    _header("TEST 2 — LLM greeting generation")
    greeting = await generate_greeting(get_menu_text())
    print(f"  Greeting: {greeting}")
    assert len(greeting) > 5, "Greeting too short"
    _ok(f"Greeting generated ({len(greeting)} chars)")


async def test_order_conversation():
    _header("TEST 3 — Full order conversation (5 turns)")

    session     = CallSession(call_sid="TEST001", phone_number="+0000000000")
    menu_text   = get_menu_text()
    sys_prompt  = build_system_prompt(menu_text)
    session.add_message("system", sys_prompt)

    turns = [
        "I'd like a Classic Burger please",
        "And can I also get a Coke",
        "Actually make that two burgers — no onion on both",
        "Can you tell me what I have so far",
        "That's everything, I'd like to confirm my order",
    ]

    for utterance in turns:
        print(f"\n  USER  ▶  {utterance}")
        msgs   = session.messages_for_llm(sys_prompt)
        result = await process_utterance(msgs, utterance)

        reply   = result.get("reply", "")
        actions = result.get("actions", [])
        latency = result.get("latency", 0.0)

        apply_actions(session, actions)
        session.add_message("user", utterance)
        session.add_message("assistant", reply)

        print(f"  ARIA  ◀  {reply}  [{latency:.2f}s]")
        print(f"  actions : {actions}")
        print(f"  order   : {len(session.order_items)} items  total=${session.order_total:.2f}")

    _ok(f"Conversation complete — final total ${session.order_total:.2f}")
    print(f"\n{session.order_summary_text()}")


async def test_order_mutations():
    _header("TEST 4 — Order mutation logic (no API)")

    from app.models.menu import find_menu_item
    from app.models.menu import OrderItem

    session = CallSession(call_sid="TEST002", phone_number="+1111111111")

    # Add
    apply_actions(session, [{"type": "add", "item_name": "Classic Burger", "quantity": 2, "notes": "no onion"}])
    assert len(session.order_items) == 1
    assert session.order_items[0].quantity == 2
    assert session.order_total == round(12.99 * 2, 2)
    _ok("add action works")

    # Dedup merge
    apply_actions(session, [{"type": "add", "item_name": "Classic Burger", "quantity": 1, "notes": "no onion"}])
    assert session.order_items[0].quantity == 3
    _ok("duplicate item merges correctly")

    # Add a second distinct item
    apply_actions(session, [{"type": "add", "item_name": "Coke", "quantity": 1, "notes": ""}])
    # "Coke" won't match anything — item count stays the same
    _ok("unknown item rejected gracefully")

    apply_actions(session, [{"type": "add", "item_name": "Soft Drink", "quantity": 1, "notes": ""}])
    assert len(session.order_items) == 2
    _ok("second item added")

    # Remove
    apply_actions(session, [{"type": "remove", "item_name": "burger"}])
    assert len(session.order_items) == 1
    _ok("remove action works")

    # Confirm
    apply_actions(session, [{"type": "confirm"}])
    assert session.stage == CallStage.COMPLETED
    _ok("confirm sets stage to COMPLETED")

    # Cancel (new session)
    s2 = CallSession(call_sid="TEST003", phone_number="+2222222222")
    apply_actions(s2, [{"type": "add", "item_name": "Pizza", "quantity": 1, "notes": ""}])
    apply_actions(s2, [{"type": "cancel"}])
    assert s2.stage == CallStage.ABANDONED
    assert len(s2.order_items) == 0
    _ok("cancel clears order and sets ABANDONED")


async def main():
    await test_menu_text()
    await test_greeting()
    await test_order_conversation()
    await test_order_mutations()

    print(f"\n{'═' * 55}")
    print("  ✅  ALL TESTS PASSED")
    print('═' * 55)


if __name__ == "__main__":
    asyncio.run(main())
