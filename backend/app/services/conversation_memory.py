"""
Conversation Memory — SQLite-backed session persistence.

Replaces the in-memory _sessions dict so conversations survive
backend restarts. Auto-cleanup old sessions after 7 days.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import os
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_DB_PATH = os.path.join(_DB_DIR, "conversations.db")

# ── Default session structure ────────────────────────────────────────

_DEFAULT_SESSION: dict[str, Any] = {
    "history": [],
    "pending_action": None,
    "pending_data": None,
    "last_search": None,
    "last_results_count": 0,
}


class ConversationMemory:
    """Thread-safe SQLite-backed conversation store.

    Usage:
        mem = ConversationMemory()
        session = mem.get_session("abc123")
        session["history"].append(...)
        mem.save_session("abc123", session)
    """

    def __init__(self, db_path: str = _DB_PATH) -> None:
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    # ── Connection management (thread-safe) ────────────────────────

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        """Create table if not exists."""
        conn = self._conn
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_updated
            ON conversations(updated_at)
        """)
        conn.commit()

    # ── CRUD ───────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Get session dict. Creates default if not exists.

        Always returns a mutable dict — call save_session() to persist.
        """
        if not session_id:
            return dict(_DEFAULT_SESSION)

        conn = self._conn
        row = conn.execute(
            "SELECT data FROM conversations WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if row is None:
            # Create new session
            data = dict(_DEFAULT_SESSION)
            conn.execute(
                "INSERT INTO conversations (session_id, data) VALUES (?, ?)",
                (session_id, json.dumps(data, ensure_ascii=False)),
            )
            conn.commit()
            return data

        try:
            data = json.loads(row["data"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("Corrupt session %s, resetting", session_id)
            data = dict(_DEFAULT_SESSION)

        # Ensure all default keys exist (new fields added after session created)
        for k, v in _DEFAULT_SESSION.items():
            if k not in data:
                data[k] = v

        return data

    def save_session(self, session_id: str, data: dict) -> None:
        """Persist session dict to database."""
        if not session_id:
            return

        conn = self._conn
        conn.execute(
            """INSERT INTO conversations (session_id, data, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(session_id) DO UPDATE SET
                   data = excluded.data,
                   updated_at = CURRENT_TIMESTAMP""",
            (session_id, json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()

    def delete_session(self, session_id: str) -> None:
        """Remove a specific session."""
        if not session_id:
            return
        conn = self._conn
        conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        conn.commit()

    def cleanup_old(self, days: int = 7) -> int:
        """Delete sessions older than N days. Returns count deleted."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        conn = self._conn
        cursor = conn.execute(
            "DELETE FROM conversations WHERE updated_at < ?",
            (cutoff,),
        )
        conn.commit()
        deleted = cursor.rowcount
        if deleted:
            logger.info("Cleaned up %d old sessions (>%d days)", deleted, days)
        return deleted

    def count_sessions(self) -> int:
        """Total sessions in DB."""
        row = self._conn.execute("SELECT COUNT(*) AS n FROM conversations").fetchone()
        return row["n"] if row else 0

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """List recent sessions (for admin/debug)."""
        rows = self._conn.execute(
            "SELECT session_id, created_at, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Singleton ────────────────────────────────────────────────────────

_instance: ConversationMemory | None = None


def get_memory() -> ConversationMemory:
    global _instance
    if _instance is None:
        _instance = ConversationMemory()
    return _instance
