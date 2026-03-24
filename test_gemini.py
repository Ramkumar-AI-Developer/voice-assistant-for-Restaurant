"""
Full end-to-end test of the Gemini Live API audio pipeline.
Sends a greeting, receives audio, then sends REAL audio back to test if Gemini responds.
"""
import asyncio
import struct
import math
from app.config import settings
from google import genai
from google.genai import types

async def test():
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    model = "gemini-2.5-flash-native-audio-latest"
    
    _TOOLS = [{"function_declarations": [{"name": "test_tool", "description": "test"}]}]
    
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text="You are a helpful restaurant assistant. Keep replies short.")]
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
    )
    
    print(f"Connecting to {model}...")
    async with client.aio.live.connect(model=model, config=config) as session:
        print("✅ Connected!")
        
        # === PHASE 1: Send text greeting and receive audio ===
        print("\n--- Phase 1: Text greeting ---")
        await session.send(input="Hello! Please greet the user.", end_of_turn=True)
        
        greeting_audio_bytes = 0
        greeting_responses = 0
        
        async for response in session.receive():
            greeting_responses += 1
            
            if response.server_content and response.server_content.model_turn:
                for part in response.server_content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        greeting_audio_bytes += len(part.inline_data.data)
                        print(f"  Audio chunk: {len(part.inline_data.data)} bytes, mime={part.inline_data.mime_type}")
                    if part.text:
                        text_preview = part.text[:80].replace('\n', ' ')
                        print(f"  Text: {text_preview}")
                        
            if response.server_content and response.server_content.turn_complete:
                print(f"  Turn complete! Total: {greeting_audio_bytes} audio bytes in {greeting_responses} responses")
                break
                
            if greeting_responses > 100:
                print("  (stopping after 100 responses)")
                break
        
        # === PHASE 2: Send synthetic PCM audio (a tone) to simulate user speech ===
        print("\n--- Phase 2: Sending synthetic audio (440Hz tone) ---")
        
        # Generate 2 seconds of 440Hz sine wave at 16kHz, 16-bit PCM
        sample_rate = 16000
        duration = 2.0
        frequency = 440.0
        num_samples = int(sample_rate * duration)
        
        audio_bytes = b""
        for i in range(num_samples):
            sample = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * i / sample_rate))
            audio_bytes += struct.pack('<h', sample)
        
        # Send in small chunks (like Twilio would)
        chunk_size = 640  # 20ms at 16kHz, 16-bit = 640 bytes
        chunks_sent = 0
        for offset in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[offset:offset + chunk_size]
            await session.send_realtime_input(
                audio=types.Blob(
                    data=chunk,
                    mime_type="audio/pcm;rate=16000"
                )
            )
            chunks_sent += 1
            
        print(f"  Sent {chunks_sent} audio chunks ({len(audio_bytes)} bytes total)")
        
        # === PHASE 3: Now send a text message to force a response ===
        print("\n--- Phase 3: Sending text after audio ---")
        await session.send(input="I would like to order a pizza please.", end_of_turn=True)
        
        response_audio_bytes = 0
        response_count = 0
        
        async for response in session.receive():
            response_count += 1
            
            if response.server_content and response.server_content.model_turn:
                for part in response.server_content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        response_audio_bytes += len(part.inline_data.data)
                    if part.text:
                        text_preview = part.text[:80].replace('\n', ' ')
                        print(f"  Text: {text_preview}")
            
            if response.server_content and response.server_content.turn_complete:
                print(f"  Turn complete! Total: {response_audio_bytes} audio bytes in {response_count} responses")
                break
                
            if response_count > 100:
                print("  (stopping after 100 responses)")
                break
        
        # === PHASE 4: Wait for model to respond to the audio (VAD) ===  
        print("\n--- Phase 4: Sending speech-like audio and waiting for VAD response ---")
        
        # Generate more realistic audio: 3 seconds of varying frequency
        duration2 = 3.0
        num_samples2 = int(sample_rate * duration2)
        audio_bytes2 = b""
        for i in range(num_samples2):
            freq = 200 + 300 * math.sin(2 * math.pi * 2 * i / sample_rate)  # Varying frequency
            sample = int(32767 * 0.3 * math.sin(2 * math.pi * freq * i / sample_rate))
            audio_bytes2 += struct.pack('<h', sample)
        
        for offset in range(0, len(audio_bytes2), chunk_size):
            chunk = audio_bytes2[offset:offset + chunk_size]
            await session.send_realtime_input(
                audio=types.Blob(
                    data=chunk,
                    mime_type="audio/pcm;rate=16000"
                )
            )
        print(f"  Sent {len(audio_bytes2)} bytes of audio")
        
        # Now wait a bit and send silence (to trigger end-of-speech detection)
        print("  Sending 1 second of silence...")
        silence = b'\x00' * (sample_rate * 2)  # 1 second of silence at 16kHz, 16-bit
        for offset in range(0, len(silence), chunk_size):
            chunk = silence[offset:offset + chunk_size]
            await session.send_realtime_input(
                audio=types.Blob(
                    data=chunk,
                    mime_type="audio/pcm;rate=16000"
                )
            )
        
        print("  Waiting for response...")
        try:
            response_count2 = 0
            async for response in session.receive():
                response_count2 += 1
                
                has_audio = False
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data:
                            has_audio = True
                        if part.text:
                            print(f"  Text: {part.text[:80]}")
                
                if has_audio:
                    print(f"  🎉 Got audio response #{response_count2}!")
                
                if response.server_content and response.server_content.turn_complete:
                    print(f"  Turn complete after {response_count2} responses")
                    break
                    
                if response_count2 > 100:
                    print("  (stopping after 100)")
                    break
        except Exception as e:
            print(f"  Error waiting for response: {e}")
    
    print("\n✅ Test complete!")

if __name__ == "__main__":
    asyncio.run(test())
