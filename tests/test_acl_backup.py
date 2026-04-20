"""Unit tests for the ACL snapshot backup helper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import config


@pytest.fixture()
def isolated_backup_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point `ACL_BACKUP_DIR` at a temp path per-test."""
    config.init(env_file=None, required=[])
    monkeypatch.setenv("ACL_BACKUP_DIR", str(tmp_path))
    return tmp_path


async def test_backup_writes_timestamped_json(isolated_backup_dir: Path) -> None:
    from utils.backup import backup_acl

    acl = {
        "acls": [{"action": "accept", "src": ["*"], "dst": ["*:*"]}],
        "groups": {"group:admin": ["x@y.com"]},
    }
    path = await backup_acl(acl)
    assert path.parent == isolated_backup_dir
    assert path.name.startswith("acl-backup-")
    assert path.suffix == ".json"
    assert json.loads(path.read_text()) == acl


async def test_backup_creates_missing_parents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.backup import backup_acl

    config.init(env_file=None, required=[])
    nested = tmp_path / "a" / "b" / "c"
    monkeypatch.setenv("ACL_BACKUP_DIR", str(nested))
    assert not nested.exists()
    path = await backup_acl({"acls": []})
    assert nested.exists()
    assert path.parent == nested


async def test_backup_defaults_to_local_backup_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ACL_BACKUP_DIR is unset, files land in ./backup (relative to CWD)."""
    from utils.backup import backup_acl

    config.init(env_file=None, required=[])
    monkeypatch.delenv("ACL_BACKUP_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    path = await backup_acl({"acls": []})
    assert path.parent == (tmp_path / "backup").resolve() or path.parent.name == "backup"
    assert path.exists()


async def test_backup_filename_format(isolated_backup_dir: Path) -> None:
    """Filename shape is the exact DD_MM_YYYY_HH_MM_SS that the spec calls for."""
    import re

    from utils.backup import backup_acl

    path = await backup_acl({"acls": []})
    m = re.match(r"^acl-backup-(\d{2})_(\d{2})_(\d{4})_(\d{2})_(\d{2})_(\d{2})\.json$", path.name)
    assert m, f"unexpected filename: {path.name}"
    dd, mm, yyyy, hh, mi, ss = map(int, m.groups())
    assert 1 <= dd <= 31
    assert 1 <= mm <= 12
    assert yyyy >= 2024
    assert 0 <= hh <= 23
    assert 0 <= mi <= 59
    assert 0 <= ss <= 59


async def test_backup_raises_on_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the directory can't be written (e.g. read-only mount), bubble the OSError
    up so callers fail closed rather than silently proceed with a mutation."""
    import os

    from utils.backup import backup_acl

    config.init(env_file=None, required=[])
    ro = tmp_path / "ro"
    ro.mkdir()
    os.chmod(ro, 0o500)  # read + execute, no write
    monkeypatch.setenv("ACL_BACKUP_DIR", str(ro))
    try:
        with pytest.raises((PermissionError, OSError)):
            await backup_acl({"acls": []})
    finally:
        os.chmod(ro, 0o700)  # restore so tmp_path cleanup works
