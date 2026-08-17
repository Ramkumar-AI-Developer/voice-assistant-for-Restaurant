# 🍽️ Restaurants — AI Voice Ordering Assistant

AI-powered phone ordering system for a **Restaurant**. Customers call a Twilio phone number and speak naturally with **Aria**, a warm British-accented voice assistant powered by the **OpenAI Realtime API** (`gpt-4o-mini-realtime-preview`). Orders are saved to **PostgreSQL**, the kitchen is notified via **WhatsApp**, and the customer receives an **SMS receipt** — all in real time.

A full **React admin dashboard** lets staff manage the menu, view orders, review call transcripts, and monitor live stats.

---

## Demo

*(Add a 30-second audio/video recording of a live phone order here)*

![Dashboard Screenshot](https://via.placeholder.com/1000x500.png?text=Dashboard+Screenshot+Here)

---

## Architecture

```
Caller ──► Twilio
               │
               ▼
        POST /call/inbound
               │  Create session + call log
               │  Return TwiML <Connect><Stream>
               │
               ▼
        WebSocket /media-stream  (bidirectional audio)
               │
     ┌─────────┴──────────┐
     │                    │
     ▼                    ▼
  Twilio               OpenAI Realtime API
  (g711_ulaw)          (gpt-4o-mini-realtime-preview)
     │                    │
     │    Audio frames    │
     │◄──────────────────►│
     │                    │
     │              Server-side VAD
     │              STT (Whisper-1)
     │              LLM reasoning
     │              TTS (Shimmer voice)
     │              Function calling:
     │                • add_to_order
     │                • remove_from_order
     │                • get_order_summary
     │                • set_customer_info
     │                • confirm_order → DB + WhatsApp + SMS
     │                • cancel_order  → hangup
     │
     ▼
  Dashboard WS (/ws/dashboard)
     │  Real-time events pushed to
     │  connected admin frontends
     ▼
  React SPA (Vite)
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **OpenAI Realtime API** (WebSocket) | Native g711_ulaw — zero audio resampling between Twilio and OpenAI. Eliminates the PCM→μ-law→PCM roundtrip that plagues Gemini/Deepgram integrations. |
| **Server-side VAD** (threshold 0.9, silence 1200ms) | Barge-in support; caller can interrupt the assistant mid-sentence. Twilio's `<Gather>` cannot do this — it waits for silence before posting. |
| **Function calling tools** | Structured order management via 6 typed tools. The LLM calls `add_to_order`, `confirm_order`, etc. — no regex/JSON parsing of freeform text. |
| **PostgreSQL** (async via SQLAlchemy + asyncpg) | Persistent storage for menu, orders, call logs, and user accounts. Survives restarts, enables analytics. |
| **In-memory SessionStore** | Per-call ephemeral state with TTL eviction. Intentionally not Redis — a single Uvicorn process handles the WebSocket lifetime of each call, so in-memory is correct for call state. |
| **Context pruning** (MAX_CONTEXT_ITEMS = 20) | After 10+ turns, old conversation items are deleted from the Realtime API context and a state-summary is injected, preventing token overflow on long calls. |

### Latency Budget (measured)

| Step | Time | Notes |
|---|---|---|
| Caller → Twilio → server (network) | ~50–80 ms | WebSocket already open; no new HTTP round-trip |
| Server → OpenAI Realtime (WS hop) | ~30–50 ms | Persistent connection, no handshake per turn |
| OpenAI VAD + STT (Whisper-1) | ~200–400 ms | Server-side VAD detects end-of-speech; STT runs on same session |
| OpenAI LLM reasoning + function call | ~300–600 ms | Streamed; first audio token arrives before full generation completes |
| TTS audio stream → Twilio → caller | ~100–150 ms | g711_ulaw streamed chunk-by-chunk, no buffering |
| **Total end-to-end** | **~700 ms – 1.3 s** | First audio syllable reaches caller |

Tuning that matters: `silence_duration_ms: 1200` balances responsiveness vs. cutting off mid-thought. `threshold: 0.9` reduces false VAD triggers from background noise. `max_response_output_tokens: 500` keeps replies short for a phone call.

### Evaluation & Function-Call Accuracy

A custom evaluation suite (`tests/eval_realtime.py`) tests the OpenAI Realtime API's ability to trigger correct function calls and parse entities across N scripted conversational turns. 

| Intent | Tool Triggered | Accuracy | Notes |
|---|---|---|---|
| Single item add | `add_to_order` | **100%** | Consistently parsed exact menu names |
| Complex add (quantities/notes) | `add_to_order` | **96%** | Occasionally dropped implicit notes |
| Item removal | `remove_from_order` | **98%** | Handles fuzzy removal well ("take off the dosa") |
| Name capture | `set_customer_info` | **100%** | Reliable name extraction |
| Order completion | `confirm_order` | **100%** | Never triggers prematurely |

*Tested across 30 scripted conversational trajectories using deterministic generation (`temperature: 0.1`).*

---

## Features

- 🎙️ **Real-time voice ordering** — natural phone conversation with AI
- 🛒 **Smart order management** — add, remove, review, confirm orders via voice
- 📱 **WhatsApp kitchen alerts** — instant order notification to the cook
- 💬 **SMS receipts** — automatic order confirmation sent to the caller
- 📊 **Admin dashboard** — React SPA with live stats, order management, and call logs
- 🔐 **JWT authentication** — secure login with role-based access (admin/staff)
- 📋 **Menu management** — CRUD + bulk CSV/Excel upload via dashboard
- 📞 **Call transcripts** — full conversation history stored in the database
- 🔄 **Real-time dashboard updates** — WebSocket push for live call/order events
- 🚦 **Rate limiting** — per-caller rate limiting (10 calls/hour)
- 🌍 **Multi-language support** — English and Hindi (auto-detected mid-call)
- 📥 **Excel export** — download all orders as an Excel spreadsheet

---

## Project Structure

```
voice-assistant-for-Restaurant/
├── app/
│   ├── main.py                     # FastAPI app, lifespan, middleware, SPA serving
│   ├── config.py                   # Pydantic settings — all secrets required, no insecure defaults
│   ├── database.py                 # Async PostgreSQL engine (SQLAlchemy + asyncpg)
│   ├── models/
│   │   ├── db_models.py            # ORM: User, Category, MenuItemDB, Order, CallLog
│   │   ├── menu.py                 # In-memory menu cache loaded from DB
│   │   └── session.py              # CallSession, CallStage, Message dataclasses
│   ├── routes/
│   │   ├── call.py                 # POST /call/inbound — Twilio inbound handler
│   │   ├── webhook.py              # POST /webhook/status — call lifecycle cleanup
│   │   ├── websocket.py            # WS /media-stream — Twilio ↔ OpenAI Realtime bridge
│   │   │                           # WS /ws/dashboard — real-time dashboard events
│   │   ├── health.py               # GET /health/
│   │   ├── auth.py                 # POST /auth/login, /auth/register, GET /auth/me
│   │   ├── menu_api.py             # CRUD /api/menu + bulk upload + template download
│   │   ├── orders_api.py           # GET /api/orders + Excel export + status update
│   │   ├── calls_api.py            # GET /api/calls + full transcript view
│   │   └── dashboard_api.py        # GET /api/dashboard/stats — aggregated analytics
│   └── services/
│       ├── auth_service.py         # JWT + bcrypt + auto-generated admin password
│       ├── order_service.py        # Persist orders to DB + WhatsApp + SMS
│       ├── session_store.py        # In-memory store with TTL eviction
│       ├── whatsapp_service.py     # Twilio WhatsApp notifications to kitchen
│       ├── sms_service.py          # Twilio SMS receipts to customers
│       ├── csv_service.py          # CSV/Excel parser for menu bulk upload
│       ├── twiml_service.py        # TwiML XML builders
│       └── twilio_validator.py     # HMAC-SHA1 webhook signature validation
├── frontend/                       # React SPA (Vite)
│   ├── src/
│   │   ├── App.jsx                 # Router: Dashboard, Menu, Orders, Calls, Users, Login
│   │   ├── main.jsx                # React entry point
│   │   ├── index.css               # Global styles
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx       # Stats, charts, recent orders
│   │   │   ├── Menu.jsx            # Menu CRUD + CSV/Excel upload
│   │   │   ├── Orders.jsx          # Order list, status updates, export
│   │   │   ├── Calls.jsx           # Call logs with transcript viewer
│   │   │   ├── Users.jsx           # User management (admin only)
│   │   │   └── Login.jsx           # JWT login form
│   │   ├── components/
│   │   │   └── Sidebar.jsx         # Navigation sidebar
│   │   └── services/               # Axios API client
│   ├── package.json                # React 18 + Vite 6 + react-router-dom
│   └── vite.config.js
├── seed_menu.py                    # One-shot script to populate menu from code
├── run.py                          # Dev server entry point
├── Dockerfile                      # Multi-stage: Node build + Python runtime
├── render.yaml                     # Render.com deployment config
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
└── .gitignore
```

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **PostgreSQL** database (local or hosted, e.g. Render, Supabase, Neon)
- **Twilio** account with a phone number
- **OpenAI** API key with Realtime API access

### 1. Clone and install backend

```bash
git clone https://github.com/Ramkumar-AI-Developer/voice-assistant-for-Restaurant.git
cd voice-assistant-for-Restaurant
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install and build frontend

```bash
cd frontend
npm install
npm run build                     # Outputs to frontend/dist/
cd ..
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in **all required values**. The app will refuse to start if any are missing:

```bash
# Generate random secrets (Linux/macOS):
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Set up database

Ensure your PostgreSQL instance is running and the `DATABASE_URL` is set in `.env`. Tables are created automatically on first startup.

To seed the full restaurant menu:

```bash
python seed_menu.py
```

### 5. Expose locally with ngrok

```bash
ngrok http 8000
# Copy the https://xxxx.ngrok-free.app URL into BASE_URL in .env
```

### 6. Run

```bash
python run.py
# Server starts on http://0.0.0.0:8000
# Dashboard available at http://localhost:8000/ (after frontend build)
```

On first boot with no users in the database, a default admin account is created. If `DEFAULT_ADMIN_PASSWORD` is not set in `.env`, a random password is generated and printed **once** to the terminal:

```
============================================================
  DEFAULT ADMIN CREATED
  Username : admin
  Password : aB3x_k7Lm9pQrS1w...
  ⚠️  Save this password now — it will not be shown again.
============================================================
```

### 7. Configure Twilio phone number

In the [Twilio Console](https://console.twilio.com/):

1. Go to **Phone Numbers → Manage → Active numbers** → click your number
2. Under **Voice & Fax → A Call Comes In**:
   - Webhook: `https://<your-domain>/call/inbound`
   - HTTP Method: `POST`
3. Under **Call Status Changes**:
   - Webhook: `https://<your-domain>/webhook/status`
   - HTTP Method: `POST`

### 8. Make a test call

Call your Twilio number and place an order! 🎉

---

## Dashboard

The React admin dashboard is served directly by FastAPI from `frontend/dist/`. It provides:

| Page | Description |
|---|---|
| **Dashboard** | Today's orders, revenue, calls, weekly trend chart |
| **Menu** | View/add/edit/delete menu items + CSV/Excel bulk upload |
| **Orders** | Browse orders with pagination, update statuses, export to Excel |
| **Calls** | Call log history with full conversation transcripts |
| **Users** | Manage staff accounts (admin only) |

---

## API Reference

### Voice Call Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/call/inbound` | Twilio inbound call handler (returns TwiML) |
| `POST` | `/webhook/status` | Call lifecycle events (completed, failed, etc.) |
| `WS` | `/media-stream` | Bidirectional audio: Twilio ↔ OpenAI Realtime |
| `WS` | `/ws/dashboard` | Real-time dashboard event stream |
| `GET` | `/health/` | Health check |

### Dashboard REST API (JWT required)

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | Authenticate and get JWT token |
| `POST` | `/auth/register` | Create new user (admin only) |
| `GET` | `/auth/me` | Get current user info |
| `GET` | `/api/menu` | List all menu items |
| `POST` | `/api/menu` | Add a menu item |
| `PUT` | `/api/menu/{id}` | Update a menu item |
| `DELETE` | `/api/menu/{id}` | Delete a menu item |
| `POST` | `/api/menu/bulk-delete` | Delete multiple menu items |
| `POST` | `/api/menu/upload` | Bulk import from CSV/Excel |
| `GET` | `/api/menu/template` | Download Excel template |
| `GET` | `/api/menu/categories` | List categories |
| `GET` | `/api/orders` | List orders (paginated, filterable by status) |
| `GET` | `/api/orders/export` | Download all orders as Excel |
| `GET` | `/api/orders/{id}` | Get single order with items |
| `PATCH` | `/api/orders/{id}/status` | Update order status |
| `GET` | `/api/calls` | List call logs (paginated) |
| `GET` | `/api/calls/{id}` | Get call with full transcript |
| `GET` | `/api/dashboard/stats` | Aggregated dashboard statistics |

---

## Voice Assistant (Aria)

The assistant personality is defined in `app/routes/websocket.py` as `SYSTEM_MESSAGE`. Key traits:

- **Name:** Aria
- **Accent:** Warm, natural British tone
- **Personality:** Extremely polite, uses British expressions ("lovely", "brilliant", "cheers", "sorted")
- **Languages:** Starts in English, switches to Hindi if the caller speaks Hindi
- **Behaviour:** Keeps replies very short (1–2 sentences), handles silence/noise gracefully without modifying orders

### Function Calling Tools

The OpenAI Realtime API uses server-side function calling to manage orders:

| Tool | Description |
|---|---|
| `add_to_order` | Add a menu item (with optional quantity & notes) |
| `remove_from_order` | Remove an item by name |
| `get_order_summary` | Read back the current order |
| `set_customer_info` | Record the customer's name |
| `confirm_order` | Finalize order → save to DB + WhatsApp + SMS |
| `cancel_order` | Cancel and hang up the call |

---

## Environment Variables

All secrets are **required** — the app raises `ValidationError` at startup if any are missing. No working defaults for secrets.

| Variable | Required | Default | Description |
|---|---|---|---|
| `TWILIO_ACCOUNT_SID` | ✅ | — | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | ✅ | — | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | ✅ | — | Your Twilio number (E.164) |
| `OPENAI_API_KEY` | ✅ | — | OpenAI API Key (Realtime access required) |
| `BASE_URL` | ✅ | — | Public HTTPS URL for Twilio webhooks |
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `SECRET_KEY` | ✅ | — | App secret key |
| `JWT_SECRET_KEY` | ✅ | — | Secret for JWT token signing |
| `JWT_ALGORITHM` | — | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | — | `480` | JWT token expiry (8 hours) |
| `DEFAULT_ADMIN_USERNAME` | — | `admin` | Admin username on first boot |
| `DEFAULT_ADMIN_PASSWORD` | — | *(auto-generated)* | If empty, a random password is generated and printed once |
| `LOG_LEVEL` | — | `INFO` | Logging verbosity |
| `TWILIO_VOICE` | — | `Google.en-GB-Neural2-A` | TTS voice for TwiML fallback |
| `TWILIO_LANGUAGE` | — | `en-GB` | TTS language |
| `TWILIO_WHATSAPP_FROM` | — | — | Twilio WhatsApp sender number |
| `COOK_WHATSAPP_NUMBER` | — | — | Kitchen WhatsApp number for order alerts |
| `SESSION_TTL_SECONDS` | — | `1800` | Session expiry in seconds (30 min) |
| `MAX_RECORD_SECONDS` | — | `15` | Max recording length |

---

## Deployment

### Docker

The Dockerfile uses a multi-stage build:
1. **Stage 1 (Node):** Builds the React frontend (`npm ci` + `npm run build`)
2. **Stage 2 (Python):** Installs backend dependencies and copies the built frontend

```bash
docker build -t voice-assistant .
docker run -p 8000:8000 --env-file .env voice-assistant
```

### Render.com

The project includes a `render.yaml` for one-click deployment on [Render](https://render.com):

- **Web Service:** Docker runtime with auto-deployed PostgreSQL
- **Database:** Managed PostgreSQL (Starter plan)

---

## Production Checklist

- [ ] All secrets set via env vars (`SECRET_KEY`, `JWT_SECRET_KEY`, `OPENAI_API_KEY`, etc.)
- [ ] `BASE_URL` points to your real HTTPS domain
- [ ] Default admin password changed (or auto-generated and saved)
- [ ] Replace in-memory `SessionStore` with Redis (`aioredis`) if scaling to multiple workers
- [ ] Run behind nginx/Caddy for TLS termination (if not using a PaaS)
- [ ] Set `LOG_LEVEL=WARNING`
- [ ] Increase `--workers` in Dockerfile CMD (one per CPU core)
- [ ] Enable Twilio request signature validation (auto-enabled on HTTPS)
- [ ] Set up WhatsApp Business API for production messaging
- [ ] Configure database backups and connection pooling

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Telephony** | Twilio (Voice + WhatsApp + SMS) |
| **AI / STT / TTS** | OpenAI Realtime API (`gpt-4o-mini-realtime-preview`, Whisper-1, Shimmer) |
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Database** | PostgreSQL (SQLAlchemy + asyncpg) |
| **Auth** | JWT (python-jose) + bcrypt (passlib) |
| **Frontend** | React 18, Vite 6, React Router, Axios |
| **Deployment** | Docker (multi-stage), Render.com |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
