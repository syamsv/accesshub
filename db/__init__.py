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
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        TEXT NOT NULL,
    device         TEXT,
    duration       TEXT NOT NULL,
    reason         TEXT,
    status         TEXT NOT NULL DEFAULT 'pending',
    created_at     TEXT NOT NULL,
    decided_at     TEXT,
    decided_by     TEXT,
    grant_state    TEXT,
    granted_at     TEXT,
    expires_at     TEXT,
    revoked_at     TEXT,
    creation_epoch INTEGER,
    acl_group_name TEXT,
    acl_tag_name   TEXT,
    acl_dst        TEXT
)
"""

# Idempotent migrations for databases created before the lifecycle columns
# existed. Re-running on an already-migrated DB is a no-op.
_MIGRATIONS = (
    "ALTER TABLE access_requests ADD COLUMN grant_state TEXT",
    "ALTER TABLE access_requests ADD COLUMN granted_at TEXT",
    "ALTER TABLE access_requests ADD COLUMN expires_at TEXT",
    "ALTER TABLE access_requests ADD COLUMN revoked_at TEXT",
    "ALTER TABLE access_requests ADD COLUMN creation_epoch INTEGER",
    "ALTER TABLE access_requests ADD COLUMN acl_group_name TEXT",
    "ALTER TABLE access_requests ADD COLUMN acl_tag_name TEXT",
    "ALTER TABLE access_requests ADD COLUMN acl_dst TEXT",
)


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
        for ddl in _MIGRATIONS:
            try:
                await conn.execute(ddl)
            except aiosqlite.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
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


# ---------------------------------------------------------------------------
# Grant / revoke lifecycle
# ---------------------------------------------------------------------------


async def set_grant_state(request_id: str, state: str) -> None:
    """Low-level state write. Use the specific helpers below where possible."""
    conn = await _get_conn()
    await conn.execute(
        "UPDATE access_requests SET grant_state = ? WHERE id = ?",
        (state, int(request_id)),
    )
    await conn.commit()


async def mark_granted(
    request_id: str,
    *,
    creation_epoch: int,
    expires_at: Optional[str],
    acl_group_name: str,
    acl_tag_name: Optional[str],
    acl_dst: str,
) -> None:
    conn = await _get_conn()
    await conn.execute(
        """
        UPDATE access_requests
        SET grant_state = 'active',
            granted_at = ?,
            expires_at = ?,
            creation_epoch = ?,
            acl_group_name = ?,
            acl_tag_name = ?,
            acl_dst = ?
        WHERE id = ?
        """,
        (
            _now(),
            expires_at,
            creation_epoch,
            acl_group_name,
            acl_tag_name,
            acl_dst,
            int(request_id),
        ),
    )
    await conn.commit()


async def mark_revoked(request_id: str) -> None:
    conn = await _get_conn()
    await conn.execute(
        "UPDATE access_requests SET grant_state = 'revoked', revoked_at = ? WHERE id = ?",
        (_now(), int(request_id)),
    )
    await conn.commit()


async def list_active_grants() -> list[dict[str, Any]]:
    """Rows with an active ACL rule that may need revoking."""
    conn = await _get_conn()
    async with conn.execute(
        "SELECT * FROM access_requests WHERE grant_state = 'active' ORDER BY expires_at"
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
