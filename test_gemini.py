import asyncio
from app.config import settings
from google import genai

async def test():
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config={'response_modalities': ['AUDIO']}) as s:
            print("SUCCESS 2.5 NATIVE AUDIO !!")
    except Exception as e:
        print(f"FAILED 2.5: {e}")

if __name__ == "__main__":
    asyncio.run(test())
