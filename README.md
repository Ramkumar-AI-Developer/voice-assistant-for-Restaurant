# 🍽️ Vasantha Vilas — AI Voice Ordering Assistant

AI-powered phone ordering system for **Vasantha Vilas** Indian Vegetarian Restaurant. Customers call a Twilio phone number and speak naturally with **Aria**, a warm British-accented voice assistant powered by the **OpenAI Realtime API** (`gpt-4o-mini-realtime-preview`). Orders are saved to **PostgreSQL**, the kitchen is notified via **WhatsApp**, and the customer receives an **SMS receipt** — all in real time.

A full **React admin dashboard** lets staff manage the menu, view orders, review call transcripts, and monitor live stats.

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
| **OpenAI Realtime API** (WebSocket) | Native g711_ulaw — zero audio resampling, sub-second latency |
| **Server-side VAD** | Barge-in support; caller can interrupt the assistant mid-sentence |
| **Function calling tools** | Structured order management; the LLM calls `add_to_order`, `confirm_order`, etc. |
| **PostgreSQL** (async via SQLAlchemy + asyncpg) | Persistent storage for menu, orders, call logs, and user accounts |
| **In-memory SessionStore** | Per-call ephemeral state with TTL eviction (swap for Redis in production) |

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
│   ├── config.py                   # Pydantic settings (env vars)
│   ├── database.py                 # Async PostgreSQL engine (SQLAlchemy + asyncpg)
│   ├── models/
│   │   ├── db_models.py            # ORM: User, Category, MenuItemDB, Order, CallLog
│   │   ├── menu.py                 # In-memory menu cache loaded from DB
│   │   └── session.py              # CallSession, CallStage, Message dataclasses
│   ├── routes/
│   │   ├── call.py                 # POST /call/inbound — Twilio inbound handler
│   │   ├── webhook.py              # POST /webhook/status — call lifecycle cleanup
│   │   ├── websocket.py            # WS /media-stream — Twilio ↔ OpenAI bridge
│   │   │                           # WS /ws/dashboard — real-time dashboard events
│   │   ├── health.py               # GET /health/
│   │   ├── auth.py                 # POST /auth/login, /auth/register, GET /auth/me
│   │   ├── menu_api.py             # CRUD /api/menu + bulk upload + template download
│   │   ├── orders_api.py           # GET /api/orders + Excel export + status update
│   │   ├── calls_api.py            # GET /api/calls + full transcript view
│   │   └── dashboard_api.py        # GET /api/dashboard/stats — aggregated analytics
│   ├── services/
│   │   ├── auth_service.py         # JWT + bcrypt password hashing + admin creation
│   │   ├── order_service.py        # Persist orders to DB + WhatsApp + SMS
│   │   ├── session_store.py        # In-memory store with TTL eviction
│   │   ├── whatsapp_service.py     # Twilio WhatsApp notifications to kitchen
│   │   ├── sms_service.py          # Twilio SMS receipts to customers
│   │   ├── csv_service.py          # CSV/Excel parser for menu bulk upload
│   │   ├── twiml_service.py        # TwiML XML builders
│   │   └── twilio_validator.py     # HMAC-SHA1 webhook signature validation
│   └── utils/
│       └── audio.py                # g711 ↔ PCM conversion utilities (legacy/Gemini)
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
├── tests/
│   └── test_pipeline.py            # Smoke tests
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
# Edit .env — fill in all required values (see Environment Variables below)
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

**Default admin credentials:**
- Username: `admin`
- Password: `admin123`

> ⚠️ Change these immediately in production via `DEFAULT_ADMIN_USERNAME` and `DEFAULT_ADMIN_PASSWORD` env vars.

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

| Variable | Required | Default | Description |
|---|---|---|---|
| `TWILIO_ACCOUNT_SID` | ✅ | — | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | ✅ | — | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | ✅ | — | Your Twilio number (E.164) |
| `OPENAI_API_KEY` | ✅ | — | OpenAI API Key (Realtime access required) |
| `BASE_URL` | ✅ | — | Public HTTPS URL for Twilio webhooks |
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `JWT_SECRET_KEY` | — | `change-me-jwt-secret-key` | Secret for JWT token signing |
| `JWT_ALGORITHM` | — | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | — | `480` | JWT token expiry (8 hours) |
| `DEFAULT_ADMIN_USERNAME` | — | `admin` | Default admin username (first boot) |
| `DEFAULT_ADMIN_PASSWORD` | — | `admin123` | Default admin password (first boot) |
| `SECRET_KEY` | — | `change-me` | App secret key |
| `LOG_LEVEL` | — | `INFO` | Logging verbosity |
| `TWILIO_VOICE` | — | `Google.en-GB-Neural2-A` | TTS voice for TwiML fallback |
| `TWILIO_LANGUAGE` | — | `en-GB` | TTS language |
| `TWILIO_WHATSAPP_FROM` | — | `whatsapp:+14155238886` | Twilio WhatsApp sender |
| `COOK_WHATSAPP_NUMBER` | — | `whatsapp:+447349035450` | Kitchen WhatsApp number |
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

- [ ] Set `BASE_URL` to your real HTTPS domain
- [ ] Set strong `SECRET_KEY` and `JWT_SECRET_KEY` values
- [ ] Change default admin credentials via env vars
- [ ] Replace in-memory `SessionStore` with Redis (`aioredis`)
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

This project is proprietary. All rights reserved.
