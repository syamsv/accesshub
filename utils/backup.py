"""ACL snapshot backups.

Callers fetch the live Tailscale policy file, then (before applying any
local mutation) hand the dict to :func:`backup_acl`. We persist it to
``ACL_BACKUP_DIR`` (env, default ``./backup``) named
``acl-backup-<DD_MM_YYYY_HH_MM_SS>.json`` so an operator can diff or
roll back by hand if a grant/cleanup cycle ever writes something wrong.

The disk write runs on a worker thread via :func:`asyncio.to_thread`
so the caller is never blocked on I/O.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger(__name__)

_FILENAME_FMT = "acl-backup-%d_%m_%Y_%H_%M_%S.json"
_DEFAULT_DIR = "backup"


def _backup_dir() -> Path:
    raw = config.get("ACL_BACKUP_DIR", _DEFAULT_DIR) or _DEFAULT_DIR
    return Path(raw).expanduser()


def _write_snapshot(path: Path, payload: str) -> None:
    # Runs on a worker thread — keep it stdlib-only to avoid pulling
    # the event loop into file I/O.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


async def backup_acl(acl_dict: dict[str, Any]) -> Path:
    """Write a timestamped JSON snapshot of ``acl_dict`` and return its path.

    Raises on disk errors — callers should fail closed (do not mutate
    the live ACL if we couldn't take a backup first).
    """
    now = datetime.now()
    path = _backup_dir() / now.strftime(_FILENAME_FMT)
    payload = json.dumps(acl_dict, indent=2, sort_keys=True)
    await asyncio.to_thread(_write_snapshot, path, payload)
    logger.info("acl backup: wrote %s (%d bytes)", path, len(payload))
    return path
