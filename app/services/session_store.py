"""
Async in-memory session store with automatic TTL eviction.
For production: replace with Redis (e.g. aioredis).
"""

import asyncio
import logging
import time
from typing import Optional

from app.models.session import CallSession
from app.config import settings

logger = logging.getLogger(__name__)


class SessionStore:
    _sessions: dict[str, CallSession] = {}
    _lock: asyncio.Lock = asyncio.Lock()
    _cleanup_task: Optional[asyncio.Task] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @classmethod
    def init(cls) -> None:
        try:
            loop = asyncio.get_event_loop()
            cls._cleanup_task = loop.create_task(cls._eviction_loop())
            logger.info("SessionStore ready (in-memory)")
        except RuntimeError:
            pass  # no running loop at import time — first request will work fine

    @classmethod
    async def close(cls) -> None:
        if cls._cleanup_task:
            cls._cleanup_task.cancel()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    @classmethod
    async def create(cls, call_sid: str, phone_number: str) -> CallSession:
        async with cls._lock:
            session = CallSession(call_sid=call_sid, phone_number=phone_number)
            cls._sessions[call_sid] = session
            logger.info(f"Session created: {call_sid} from {phone_number}")
            return session

    @classmethod
    async def get(cls, call_sid: str) -> Optional[CallSession]:
        async with cls._lock:
            session = cls._sessions.get(call_sid)
            if session:
                session.last_active = time.time()
            return session

    @classmethod
    async def get_or_create(cls, call_sid: str, phone_number: str = "unknown") -> CallSession:
        session = await cls.get(call_sid)
        if session is None:
            session = await cls.create(call_sid, phone_number)
        return session

    @classmethod
    async def delete(cls, call_sid: str) -> None:
        async with cls._lock:
            cls._sessions.pop(call_sid, None)
            logger.info(f"Session removed: {call_sid}")

    @classmethod
    async def all_sessions(cls) -> list[dict]:
        async with cls._lock:
            return [s.to_dict() for s in cls._sessions.values()]

    # ── TTL eviction ──────────────────────────────────────────────────────────

    @classmethod
    async def _eviction_loop(cls) -> None:
        while True:
            await asyncio.sleep(60)
            now = time.time()
            ttl = settings.SESSION_TTL_SECONDS
            async with cls._lock:
                expired = [sid for sid, s in cls._sessions.items()
                           if now - s.last_active > ttl]
                for sid in expired:
                    logger.info(f"Session TTL evicted: {sid}")
                    del cls._sessions[sid]
