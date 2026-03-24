"""Test which Gemini models support the Live API (bidiGenerateContent)."""
import asyncio
from app.config import settings
from google import genai
from google.genai import types

async def test():
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    print("=== Models supporting bidiGenerateContent ===")
    for m in client.models.list():
        if hasattr(m, 'supported_actions') and m.supported_actions and 'bidiGenerateContent' in m.supported_actions:
            print(f"  {m.name}")
    
    # Test each candidate model
    candidates = [
        "gemini-2.0-flash-live-001",
        "gemini-2.5-flash-native-audio-latest",
        "gemini-2.0-flash",
    ]
    
    for model_name in candidates:
        print(f"\n--- Testing: {model_name} ---")
        try:
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
            )
            async with client.aio.live.connect(model=model_name, config=config) as session:
                print(f"  ✅ Connected successfully!")
                
                # Send a simple text and see what we get back
                await session.send(input="Say hello in one sentence.", end_of_turn=True)
                
                response_count = 0
                audio_bytes_total = 0
                
                async for response in session.receive():
                    response_count += 1
                    
                    has_data = response.data is not None
                    has_server_content = response.server_content is not None
                    has_tool_call = response.tool_call is not None
                    
                    parts_info = []
                    if has_server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.inline_data:
                                parts_info.append(f"inline_data({len(part.inline_data.data)}b, {part.inline_data.mime_type})")
                                audio_bytes_total += len(part.inline_data.data)
                            if part.text:
                                parts_info.append(f"text({part.text[:50]})")
                            if hasattr(part, 'thought') and part.thought:
                                parts_info.append("thought")
                    
                    if has_data:
                        audio_bytes_total += len(response.data)
                    
                    turn_complete = (has_server_content and 
                                   response.server_content.turn_complete)
                    
                    print(f"  Response #{response_count}: data={has_data}, server_content={has_server_content}, "
                          f"tool_call={has_tool_call}, turn_complete={turn_complete}, "
                          f"parts=[{', '.join(parts_info)}]")
                    
                    if turn_complete:
                        break
                    
                    if response_count > 50:
                        print("  (stopping after 50 responses)")
                        break
                
                print(f"  Total responses: {response_count}, Total audio bytes: {audio_bytes_total}")
                
        except Exception as e:
            print(f"  ❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
