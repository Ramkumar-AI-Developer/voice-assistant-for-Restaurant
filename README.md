# 🍽️ Restaurant Voice Call Assistant

AI-powered phone ordering system built on **Twilio**, **Groq Whisper** (`whisper-large-v3-turbo`), and **Groq LLM** (`llama-3.3-70b-versatile`).

---

## Architecture

```
Caller ──► Twilio
               │
               ▼
        POST /call/inbound
               │  Create session
               │  Groq LLM → greeting
               │  TwiML <Gather speech>
               │
               ▼
        POST /webhook/speech  ◄─────────────────────────┐
               │                                        │
        Twilio STT conf ≥ 0.75?                         │
          YES ──► use it                                │
          NO  ──► fetch recording → Groq Whisper STT    │
               │                                        │
               ▼                                        │
        Groq LLM (llama-3.3-70b-versatile)              │
          • Extract order actions (add/remove/confirm)  │
          • Generate short spoken reply                 │
          • JSON mode, streamed                         │
               │                                        │
        apply_actions() → mutate session                │
               │                                        │
        ┌──────┴──────────────┐                         │
        ▼                     ▼                         │
   COMPLETED/          still ordering                   │
   ABANDONED      listen_twiml(reply) ─────────────────►┘
        │
        ▼
  order_placed_twiml()
  Hangup
```

### Latency Budget (typical)

| Step | Time |
|---|---|
| Twilio → server (network) | ~50 ms |
| Groq Whisper STT | ~200–400 ms |
| Groq LLM 70b (streaming) | ~350–700 ms |
| TwiML → Twilio → TTS playback starts | ~100 ms |
| **Total end-to-end** | **~700 ms – 1.2 s** |

---

## Project Structure

```
restaurant-voice-assistant/
├── app/
│   ├── main.py                   # FastAPI app + lifespan
│   ├── config.py                 # All settings via env vars
│   ├── models/
│   │   ├── menu.py               # MenuItem, OrderItem, MENU dict
│   │   └── session.py            # CallSession, CallStage, Message
│   ├── routes/
│   │   ├── call.py               # POST /call/inbound
│   │   ├── webhook.py            # POST /webhook/speech|partial|confirm|status
│   │   └── health.py             # GET  /health/
│   └── services/
│       ├── stt_service.py        # Groq AsyncGroq audio.transcriptions
│       ├── llm_service.py        # Groq AsyncGroq chat.completions (streaming)
│       ├── order_service.py      # Applies LLM actions to session
│       ├── session_store.py      # Async in-memory store + TTL eviction
│       ├── twiml_service.py      # TwiML XML builders
│       └── twilio_validator.py   # HMAC-SHA1 webhook signature validation
├── tests/
│   └── test_pipeline.py          # Smoke test (no real call needed)
├── logs/
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── run.py
```

---

## Quick Start

### 1. Clone and install

```bash
cd restaurant-voice-assistant
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — fill in:
#   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_API_KEY, TWILIO_PHONE_NUMBER
#   GROQ_API_KEY
#   BASE_URL  (your public HTTPS URL — see step 3)
```

### 3. Expose locally with ngrok

```bash
ngrok http 8000
# Copy the https://xxxx.ngrok.io URL into BASE_URL in .env
```

### 4. Run

```bash
python run.py
# Server starts on http://0.0.0.0:8000
```

### 5. Configure Twilio phone number

In the [Twilio Console](https://console.twilio.com/):

1. Go to **Phone Numbers → Manage → Active numbers** → click your number
2. Under **Voice & Fax → A Call Comes In**:
   - Webhook: `https://<your-domain>/call/inbound`
   - HTTP Method: `POST`
3. Under **Call Status Changes**:
   - Webhook: `https://<your-domain>/webhook/status`
   - HTTP Method: `POST`

### 6. Smoke-test without a real call

```bash
python tests/test_pipeline.py
```

### 7. Make a test call

Call your Twilio number and place an order! 🎉

---

## Barge-in / Interrupt Handling

Twilio's `<Gather>` is configured with `partialResultCallback` — this fires a
webhook to `/webhook/partial` **while the caller is still speaking**, even during
TTS playback. The partial transcript is stored on the session (`last_partial`).

To cut TTS playback mid-sentence in production, hit the Twilio Calls API:

```python
from twilio.rest import Client
client = Client(ACCOUNT_SID, AUTH_TOKEN)
client.calls(call_sid).update(twiml=listen_twiml("Go ahead, I'm listening."))
```

---

## Customising the Menu

Edit `app/models/menu.py` — the `MENU` dict.
In production, replace `get_menu_text()` with a DB query or external API call.

---

## Production Checklist

- [ ] Set `BASE_URL` to your real HTTPS domain
- [ ] Set a strong `SECRET_KEY`
- [ ] Replace in-memory `SessionStore` with Redis (`aioredis`)
- [ ] Run behind nginx/Caddy for TLS termination
- [ ] Set `LOG_LEVEL=WARNING`
- [ ] Increase `--workers` in Dockerfile CMD (one per CPU core)
- [ ] Enable Twilio request signature validation (auto-enabled on HTTPS)
- [ ] Add `POST /webhook/recording` to store or transcribe full call audio

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TWILIO_ACCOUNT_SID` | ✅ | — | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | ✅ | — | Twilio Auth Token |
| `TWILIO_API_KEY` | ✅ | — | Twilio API Key |
| `TWILIO_PHONE_NUMBER` | ✅ | — | Your Twilio number (E.164) |
| `GROQ_API_KEY` | ✅ | — | Groq API Key |
| `BASE_URL` | ✅ | — | Public HTTPS URL for Twilio webhooks |
| `GROQ_STT_MODEL` | — | `whisper-large-v3-turbo` | Groq Whisper model |
| `GROQ_LLM_MODEL` | — | `llama-3.3-70b-versatile` | Groq LLM model |
| `TWILIO_VOICE` | — | `Polly.Joanna` | AWS Polly TTS voice |
| `SESSION_TTL_SECONDS` | — | `1800` | Session expiry (30 min) |
| `LOG_LEVEL` | — | `INFO` | Logging verbosity |
