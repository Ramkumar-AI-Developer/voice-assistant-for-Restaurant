"""
Restaurant Voice Call Assistant
────────────────────────────────
Stack:
  • Twilio          — telephony (inbound calls, TTS, STT fallback)
  • Groq Whisper    — whisper-large-v3-turbo  (primary STT)
  • Groq LLM        — llama-3.3-70b-versatile (NLU + response generation)
  • FastAPI/uvicorn — async HTTP server
  • PostgreSQL      — persistent storage (menu, orders, call logs)
  • Twilio WhatsApp — order notifications to cook
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import call, webhook, health
from app.routes import auth, menu_api, orders_api, calls_api, dashboard_api
from app.services import stt_service, llm_service
from app.services.session_store import SessionStore
from app.config import settings
from app.database import create_tables, close_db, AsyncSessionLocal
from app.models.menu import load_menu_from_db
from app.services.auth_service import create_default_admin

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log"),
    ],
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Restaurant Voice Assistant starting ...")

    # Initialize database tables
    await create_tables()

    # Create default admin user
    async with AsyncSessionLocal() as db:
        await create_default_admin(db)

    # Load menu from database
    async with AsyncSessionLocal() as db:
        await load_menu_from_db(db)

    # Initialize session store
    SessionStore.init()

    logger.info("All systems ready")
    yield

    logger.info("Shutting down ...")
    await SessionStore.close()
    await stt_service.close()
    await llm_service.close()
    await close_db()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Restaurant Voice Assistant",
    description="AI-powered restaurant ordering via phone — Twilio + Groq + PostgreSQL",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

# ── Voice call routes ─────────────────────────────────────────────────────────
app.include_router(health.router,  prefix="/health",  tags=["health"])
app.include_router(call.router,    prefix="/call",    tags=["call"])
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])

# ── Dashboard API routes ─────────────────────────────────────────────────────
app.include_router(auth.router,          prefix="/auth",          tags=["auth"])
app.include_router(menu_api.router,      prefix="/api/menu",      tags=["menu"])
app.include_router(orders_api.router,    prefix="/api/orders",    tags=["orders"])
app.include_router(calls_api.router,     prefix="/api/calls",     tags=["calls"])
app.include_router(dashboard_api.router, prefix="/api/dashboard", tags=["dashboard"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
