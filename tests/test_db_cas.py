"""Integration tests for the DB layer, against an isolated temp SQLite file.

Confirms the compare-and-swap semantics on :func:`db.set_request_decision`
and the lifecycle-column migrations run idempotently.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


@pytest.fixture()
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Hand `db` a brand-new SQLite file per test."""
    db_path = tmp_path / "accesshub.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))

    # Initialise config with no required vars.
    import config
    config.init(env_file=None, required=[])

    import db as dbmod
    importlib.reload(dbmod)
    yield dbmod
    # Best-effort cleanup. The connection is closed by the process; unlink the files.
    for f in [db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]:
        if f.exists():
            os.unlink(f)


async def test_decision_cas_accepts_first_click_rejects_second(isolated_db) -> None:
    db = isolated_db
    rid = await db.create_request(user_id="U1", device="host", duration="60", reason="x")
    assert await db.set_request_decision(rid, status="approved", decided_by="A1")
    assert not await db.set_request_decision(rid, status="denied", decided_by="A2")
    row = await db.get_request(rid)
    assert row["status"] == "approved"
    assert row["decided_by"] == "A1"


async def test_decision_invalid_status_raises(isolated_db) -> None:
    db = isolated_db
    rid = await db.create_request(user_id="U1", device="host", duration="60", reason="x")
    with pytest.raises(ValueError):
        await db.set_request_decision(rid, status="maybe", decided_by="A1")


async def test_mark_granted_populates_lifecycle_columns(isolated_db) -> None:
    db = isolated_db
    rid = await db.create_request(user_id="U1", device="host", duration="60", reason="x")
    await db.set_request_decision(rid, status="approved", decided_by="A1")
    await db.mark_granted(
        rid,
        creation_epoch=123456789,
        expires_at="2099-01-01T00:00:00+00:00",
        acl_group_name="group:accesshub-1-1-60",
        acl_dst="100.64.0.5:*",
    )
    row = await db.get_request(rid)
    assert row["grant_state"] == "active"
    assert row["acl_group_name"] == "group:accesshub-1-1-60"
    assert row["acl_dst"] == "100.64.0.5:*"
    assert row["creation_epoch"] == 123456789


async def test_list_stuck_grants_surfaces_granting_and_revoking(isolated_db) -> None:
    db = isolated_db
    rid = await db.create_request(user_id="U1", device="host", duration="60", reason="x")
    await db.set_grant_state(rid, "granting")
    stuck = await db.list_stuck_grants()
    assert any(r["id"] == int(rid) for r in stuck)

    await db.set_grant_state(rid, "revoking")
    stuck = await db.list_stuck_grants()
    assert any(r["id"] == int(rid) for r in stuck)

    await db.set_grant_state(rid, "active")
    stuck = await db.list_stuck_grants()
    assert not any(r["id"] == int(rid) for r in stuck)
