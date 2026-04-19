"""SQLite CRUD for access requests (async, aiosqlite).

A single `access_requests` table keyed by an auto-increment integer id:

    id           INTEGER PRIMARY KEY — exposed as a string to callers
    user_id      TEXT    NOT NULL   — Slack user who submitted
    device       TEXT               — hostname or tag from the modal
    duration     TEXT    NOT NULL   — minutes as string, or "permanent"
    reason       TEXT
    status       TEXT    NOT NULL DEFAULT 'pending' — pending|approved|denied
    created_at   TEXT    NOT NULL   — ISO-8601 UTC
    decided_at   TEXT
    decided_by   TEXT               — Slack user who approved/denied
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

import config

_conn: Optional[aiosqlite.Connection] = None
_init_lock = asyncio.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS access_requests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    device     TEXT,
    duration   TEXT NOT NULL,
    reason     TEXT,
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT
)
"""


async def _get_conn() -> aiosqlite.Connection:
    global _conn
    if _conn is not None:
        return _conn
    async with _init_lock:
        if _conn is not None:
            return _conn
        path = config.get("SQLITE_PATH", "accesshub.db")
        conn = await aiosqlite.connect(path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute(_SCHEMA)
        await conn.commit()
        _conn = conn
        return _conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_request(
    *,
    user_id: str,
    device: Optional[str],
    duration: str,
    reason: Optional[str],
) -> str:
    conn = await _get_conn()
    cur = await conn.execute(
        """
        INSERT INTO access_requests (user_id, device, duration, reason, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, device, duration, reason, _now()),
    )
    await conn.commit()
    return str(cur.lastrowid)


async def get_request(request_id: str) -> Optional[dict[str, Any]]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT * FROM access_requests WHERE id = ?", (int(request_id),)
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def set_request_decision(
    request_id: str, *, status: str, decided_by: str
) -> bool:
    """Record a decision on a pending request.

    Returns True if the row was pending and got updated, False if it was
    already decided (prevents double-approval on repeated button clicks).
    """
    if status not in ("approved", "denied"):
        raise ValueError(f"invalid status: {status!r}")

    conn = await _get_conn()
    cur = await conn.execute(
        """
        UPDATE access_requests
        SET status = ?, decided_by = ?, decided_at = ?
        WHERE id = ? AND status = 'pending'
        """,
        (status, decided_by, _now(), int(request_id)),
    )
    await conn.commit()
    return cur.rowcount == 1


async def list_pending() -> list[dict[str, Any]]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT * FROM access_requests WHERE status = 'pending' ORDER BY id"
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
