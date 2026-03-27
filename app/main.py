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

import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import call, webhook, health, websocket
from app.routes import auth, menu_api, orders_api, calls_api, dashboard_api

from app.services.session_store import SessionStore
from app.services.twilio_validator import validate_twilio_request
from app.config import settings
from app.database import create_tables, close_db, AsyncSessionLocal
from app.models.menu import load_menu_from_db
from app.services.auth_service import create_default_admin

# ── Structured Logging Context ───────────────────────────────────────────────
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_ctx_var.get()
        return True

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | [%(request_id)s] | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log"),
    ],
)

# Apply context filter to the root logger to catch all log messages
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestIdFilter())

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
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_ctx_var.set(req_id)
    
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    
    response.headers["X-Request-ID"] = req_id
    request_id_ctx_var.reset(token)
    return response

# ── Voice call routes ─────────────────────────────────────────────────────────
app.include_router(health.router,  prefix="/health",  tags=["health"])
app.include_router(call.router,    prefix="/call",    tags=["call"],    dependencies=[Depends(validate_twilio_request)])
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"], dependencies=[Depends(validate_twilio_request)])
app.include_router(websocket.router, tags=["websocket"])

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


# ── Serve frontend SPA (must be last) ────────────────────────────────────────
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _frontend_dist.is_dir():
    # Serve index.html for SPA routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = _frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_frontend_dist / "index.html")

    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
    logger.info(f"Serving frontend from {_frontend_dist}")
else:
    logger.warning(f"Frontend dist not found at {_frontend_dist} — dashboard won't be served")

