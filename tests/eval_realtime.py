"""
Automated Evaluation Suite for OpenAI Realtime API Function Calling.

This script runs scripted text conversations against the Realtime API
to measure function-call accuracy (intent detection, entity extraction).
It evaluates:
1. add_to_order
2. remove_from_order
3. set_customer_info
4. confirm_order
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.routes.websocket import SYSTEM_MESSAGE, ORDER_TOOLS, OPENAI_REALTIME_URL
from app.models.menu import get_menu_text
import websockets

TEST_CASES = [
    {
        "name": "Add single item",
        "input": "I'd like one Masala Dosa please.",
        "expected_tool": "add_to_order",
        "expected_args": {"item_name": "Masala Dosa", "quantity": 1}
    },
    {
        "name": "Add item with notes",
        "input": "Can I get a Filter Coffee, but make it extra strong?",
        "expected_tool": "add_to_order",
        "expected_args": {"item_name": "Filter Coffee", "quantity": 1, "notes": "extra strong"}
    },
    {
        "name": "Remove item",
        "input": "Actually, take off the Dosa.",
        "expected_tool": "remove_from_order",
        "expected_args": {"item_name": "Dosa"}
    },
    {
        "name": "Set customer info",
        "input": "My name is John Smith.",
        "expected_tool": "set_customer_info",
        "expected_args": {"name": "John Smith"}
    },
    {
        "name": "Confirm order",
        "input": "That's everything, go ahead and place the order.",
        "expected_tool": "confirm_order",
        "expected_args": {}
    }
]

async def run_eval():
    print("Starting Eval Suite against OpenAI Realtime API...")
    if not settings.OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set.")
        return

    menu_text = get_menu_text()
    instructions = SYSTEM_MESSAGE.format(menu=menu_text)

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    passed = 0
    total = len(TEST_CASES)
    
    for i, test in enumerate(TEST_CASES):
        print(f"\n[{i+1}/{total}] Running: {test['name']}")
        print(f"  User input: '{test['input']}'")
        
        try:
            async with websockets.connect(OPENAI_REALTIME_URL, additional_headers=headers) as ws:
                # 1. Init session (text only for speed)
                await ws.send(json.dumps({
                    "type": "session.update",
                    "session": {
                        "instructions": instructions,
                        "modalities": ["text"],
                        "tools": ORDER_TOOLS,
                        "tool_choice": "auto",
                        "temperature": 0.1,  # low temp for deterministic eval
                    }
                }))

                # 2. Inject user text
                await ws.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": test['input']}]
                    }
                }))

                # 3. Request response
                await ws.send(json.dumps({
                    "type": "response.create"
                }))

                # 4. Wait for function call
                got_expected = False
                actual_tool = None
                actual_args = None

                while True:
                    try:
                        msg_str = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        msg = json.loads(msg_str)
                        
                        if msg["type"] == "response.function_call_arguments.done":
                            actual_tool = msg.get("name")
                            actual_args = json.loads(msg.get("arguments", "{}"))
                            
                            # Validate
                            if actual_tool == test["expected_tool"]:
                                # Check args
                                args_match = True
                                for k, v in test["expected_args"].items():
                                    # Very basic partial match (LLM might format string slightly differently)
                                    if k not in actual_args or str(v).lower() not in str(actual_args[k]).lower():
                                        args_match = False
                                        break
                                
                                if args_match:
                                    got_expected = True
                            
                            # We got a tool call, we can break
                            break
                            
                        elif msg["type"] == "response.done":
                            # Response finished without a function call
                            break
                            
                    except asyncio.TimeoutError:
                        print("  Timed out waiting for response.")
                        break

                if got_expected:
                    print(f"  ✅ PASS (Called {actual_tool} with {actual_args})")
                    passed += 1
                else:
                    print(f"  ❌ FAIL")
                    print(f"     Expected: {test['expected_tool']} args={test['expected_args']}")
                    print(f"     Got:      {actual_tool} args={actual_args}")
                    
        except Exception as e:
            print(f"  ❌ FAIL (Error: {e})")
            
    print(f"\nEval Summary: {passed}/{total} passed ({(passed/total)*100:.1f}%)")

if __name__ == "__main__":
    asyncio.run(run_eval())
