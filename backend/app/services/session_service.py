"""
Redis-backed session service for LLM Chat Bot.

Manages:
- Conversation history per session
- Booking state machine (idle → search_results → collecting_passengers → confirmed)
- Cached search results
- TTL-based expiry (default 24h)

Falls back to in-memory dict if Redis is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try importing redis — graceful fallback if not installed/unavailable
try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis not installed — using in-memory session fallback")


# ─── In-memory fallback ─────────────────────────────────────────────────────

# Only used when Redis is unavailable
_memory_store: dict[str, dict[str, Any]] = {}
_memory_expiry: dict[str, datetime] = {}


class SessionService:
    """Session management with Redis + in-memory fallback."""

    DEFAULT_TTL_HOURS = 24
    SESSION_PREFIX = "abtrip:session:"

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._redis_available = False
        self._connected = False

    async def connect(self) -> bool:
        """Connect to Redis. Returns True if connected, False if fallback to memory."""
        if not REDIS_AVAILABLE:
            logger.info("SessionService: using in-memory store (redis not available)")
            return False

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self._redis = aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await self._redis.ping()
            self._redis_available = True
            self._connected = True
            logger.info("SessionService: connected to Redis at %s", redis_url)
            return True
        except Exception as e:
            logger.warning(
                "SessionService: Redis unavailable (%s), using in-memory fallback", e
            )
            self._redis_available = False
            self._redis = None
            self._connected = False
            return False

    async def close(self):
        """Close Redis connection if open."""
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None
            self._redis_available = False
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Session CRUD ──────────────────────────────────────────────────────

    async def create_session(
        self, agent: str = "ticketing", session_id: str | None = None
    ) -> str:
        """Create a new chat session. Returns session_id."""
        sid = session_id or str(uuid.uuid4())
        data = {
            "agent": agent,
            "messages": [],
            "step": "idle",
            "search_results": [],
            "booking_draft": {"selected_route": {}, "passengers": [], "contact": {}, "step": "idle", "error_message": ""},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._save(sid, data)
        return sid

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session data. Returns None if not found."""
        return await self._load(session_id)

    async def update_session(self, session_id: str, data: dict[str, Any]) -> bool:
        """Update entire session data."""
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        return await self._save(session_id, data)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        return await self._delete(session_id)

    # ── Conversation helpers ──────────────────────────────────────────────

    async def add_message(
        self, session_id: str, role: str, content: str, metadata: dict | None = None
    ) -> bool:
        """Add a message to session history."""
        data = await self.get_session(session_id)
        if not data:
            return False

        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        data.setdefault("messages", []).append(msg)
        # Keep last 20 messages
        data["messages"] = data["messages"][-20:]
        return await self.update_session(session_id, data)

    async def get_messages(
        self, session_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get recent conversation history."""
        data = await self.get_session(session_id)
        if not data:
            return []
        return data.get("messages", [])[-limit:]

    async def update_step(
        self, session_id: str, step: str
    ) -> bool:
        """Update the session state machine step."""
        data = await self.get_session(session_id)
        if not data:
            return False
        data["step"] = step
        return await self.update_session(session_id, data)

    async def get_step(self, session_id: str) -> str:
        """Get current session step."""
        data = await self.get_session(session_id)
        if not data:
            return "idle"
        return data.get("step", "idle")

    # ── Booking draft helpers ─────────────────────────────────────────────

    async def save_search_results(
        self, session_id: str, raw_data: dict[str, Any], formatted: str
    ) -> bool:
        """Save flight search results to session."""
        data = await self.get_session(session_id)
        if not data:
            return False

        result = {
            "raw_data": raw_data,
            "formatted": formatted,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "selected_flight_index": None,
        }
        data.setdefault("search_results", []).append(result)
        data["step"] = "search_results"
        return await self.update_session(session_id, data)

    async def get_latest_search(self, session_id: str) -> dict | None:
        """Get the most recent search results."""
        data = await self.get_session(session_id)
        if not data:
            return None
        results = data.get("search_results", [])
        return results[-1] if results else None

    async def save_booking_draft(
        self, session_id: str, draft: dict[str, Any]
    ) -> bool:
        """Save booking draft data."""
        data = await self.get_session(session_id)
        if not data:
            return False
        data["booking_draft"] = draft
        return await self.update_session(session_id, data)

    async def get_booking_draft(self, session_id: str) -> dict[str, Any]:
        """Get current booking draft."""
        data = await self.get_session(session_id)
        if not data:
            return {"selected_route": {}, "passengers": [], "contact": {}, "step": "idle", "error_message": ""}
        return data.get("booking_draft", {})

    # ── Storage backends ──────────────────────────────────────────────────

    async def _save(self, key: str, data: dict[str, Any]) -> bool:
        """Save data to Redis or in-memory."""
        serialized = json.dumps(data, default=str)
        if self._redis_available and self._redis:
            try:
                await self._redis.setex(
                    f"{self.SESSION_PREFIX}{key}",
                    timedelta(hours=self.DEFAULT_TTL_HOURS),
                    serialized,
                )
                return True
            except Exception as e:
                logger.error("Redis save failed: %s", e)
                # Fall through to memory
        # In-memory fallback
        _memory_store[key] = data
        _memory_expiry[key] = datetime.now(timezone.utc) + timedelta(
            hours=self.DEFAULT_TTL_HOURS
        )
        return True

    async def _load(self, key: str) -> dict[str, Any] | None:
        """Load data from Redis or in-memory."""
        if self._redis_available and self._redis:
            try:
                raw = await self._redis.get(f"{self.SESSION_PREFIX}{key}")
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.error("Redis load failed: %s", e)
                # Fall through to memory
        # In-memory fallback
        data = _memory_store.get(key)
        if data:
            expiry = _memory_expiry.get(key)
            if expiry and datetime.now(timezone.utc) < expiry:
                return data
            # Expired
            _memory_store.pop(key, None)
            _memory_expiry.pop(key, None)
        return None

    async def _delete(self, key: str) -> bool:
        """Delete data from Redis or in-memory."""
        if self._redis_available and self._redis:
            try:
                await self._redis.delete(f"{self.SESSION_PREFIX}{key}")
                return True
            except Exception:
                pass
        _memory_store.pop(key, None)
        _memory_expiry.pop(key, None)
        return True


# ─── Singleton ──────────────────────────────────────────────────────────────

_session_service: SessionService | None = None


def get_session_service() -> SessionService:
    """Get or create the singleton SessionService."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service


async def init_session_service():
    """Initialize session service (call on app startup)."""
    svc = get_session_service()
    await svc.connect()


async def close_session_service():
    """Close session service (call on app shutdown)."""
    svc = get_session_service()
    await svc.close()
