"""Unit tests for the cleaner's pure parsing and cleanup logic."""

from __future__ import annotations

import pytest

from cleaner.expiry import (
    apply_cleanup,
    find_expired_groups,
    is_expired,
    parse_name,
)
from tailscale.models import ACL

# Example payload from the user's production ACL.
_CREATED = 1_776_623_011  # group:accesshub-5-1776623011-60 — 60 minutes
_LIVE = 1_776_621_030     # group:accesshub-4-1776621030-150 — 150 minutes
_FAR = 1_776_623_234      # group:accesshub-6-1776623234-2880 — 48 hours


def test_parse_name_numeric() -> None:
    p = parse_name("group:accesshub-5-1776623011-60")
    assert p is not None
    assert p.request_id == 5
    assert p.creation_epoch == 1_776_623_011
    assert p.duration_label == "60"
    assert not p.is_permanent
    assert p.expires_at_epoch == 1_776_623_011 + 60 * 60


def test_parse_name_permanent() -> None:
    p = parse_name("group:accesshub-9-1700000000-permanent")
    assert p is not None
    assert p.is_permanent
    assert p.expires_at_epoch is None


@pytest.mark.parametrize(
    "name",
    [
        "group:admin",
        "group:accesshub",
        "group:accesshub-abc-123-60",
        "group:accesshub-1-1-permanent-extra",
        "tag:accesshub-1-1-60",
        "",
    ],
)
def test_parse_name_rejects_non_matching(name: str) -> None:
    assert parse_name(name) is None


def test_is_expired_numeric() -> None:
    p = parse_name("group:accesshub-5-1776623011-60")
    assert p is not None
    just_before = 1_776_623_011 + 59 * 60
    just_at = 1_776_623_011 + 60 * 60
    assert not is_expired(p, just_before)
    assert is_expired(p, just_at)  # boundary: expiry at exactly t+duration
    assert is_expired(p, just_at + 1)


def test_is_expired_permanent_never() -> None:
    p = parse_name("group:accesshub-9-1-permanent")
    assert p is not None
    assert not is_expired(p, 2**40)


def _fixture_acl() -> ACL:
    return ACL.from_dict(
        {
            "acls": [
                {
                    "action": "accept",
                    "src": ["group:accesshub-4-1776621030-150"],
                    "dst": ["tag:server:*"],
                },
                {
                    "action": "accept",
                    "src": ["group:accesshub-5-1776623011-60"],
                    "dst": ["tag:server:*"],
                },
                {
                    "action": "accept",
                    "src": ["group:accesshub-6-1776623234-2880"],
                    "dst": ["100.83.228.34:*"],
                },
            ],
            "groups": {
                "group:admin": ["syamsv2020@gmail.com"],
                "group:accesshub-4-1776621030-150": ["syamsv2020@gmail.com"],
                "group:accesshub-5-1776623011-60": ["syamsv2020@gmail.com"],
                "group:accesshub-6-1776623234-2880": ["syamsv2020@gmail.com"],
            },
            "tagOwners": {"tag:server": ["autogroup:admin", "group:admin"]},
        }
    )


def test_find_expired_groups_matches_only_past_expiry() -> None:
    acl = _fixture_acl()
    # 61 minutes after grant 5 (60 min) — expired. Grant 4 (150 min from
    # _LIVE) still has ~115 min left relative to this now.
    now = _CREATED + 61 * 60
    expired = find_expired_groups(acl, now)
    names = [p.name for p in expired]
    assert names == ["group:accesshub-5-1776623011-60"]


def test_apply_cleanup_removes_group_and_associated_rule() -> None:
    acl = _fixture_acl()
    now = _CREATED + 61 * 60
    expired = find_expired_groups(acl, now)
    apply_cleanup(acl, expired)

    out = acl.to_dict()
    assert "group:accesshub-5-1776623011-60" not in out["groups"]
    # Other groups preserved
    assert "group:admin" in out["groups"]
    assert "group:accesshub-4-1776621030-150" in out["groups"]
    # The rule whose src == the expired group is gone
    srcs = [r["src"] for r in out["acls"] if isinstance(r, dict)]
    assert ["group:accesshub-5-1776623011-60"] not in srcs
    # Other accesshub rules still present
    assert ["group:accesshub-4-1776621030-150"] in srcs


def test_apply_cleanup_noop_on_empty_expiry_list() -> None:
    acl = _fixture_acl()
    before = acl.to_dict()
    apply_cleanup(acl, [])
    assert acl.to_dict() == before


def test_apply_cleanup_preserves_multisrc_rules() -> None:
    """A rule whose src references an expired group *plus* something
    else must be kept intact — we only delete rules that are exclusively
    ours."""
    acl = ACL.from_dict(
        {
            "acls": [
                {
                    "action": "accept",
                    "src": [
                        "group:accesshub-5-1776623011-60",
                        "group:admin",  # not ours
                    ],
                    "dst": ["tag:server:*"],
                },
            ],
            "groups": {
                "group:accesshub-5-1776623011-60": ["x@y.com"],
                "group:admin": ["y@z.com"],
            },
        }
    )
    now = _CREATED + 61 * 60
    expired = find_expired_groups(acl, now)
    apply_cleanup(acl, expired)
    out = acl.to_dict()
    # Group removed
    assert "group:accesshub-5-1776623011-60" not in out["groups"]
    # Multi-src rule preserved — operator problem to clean up
    assert len(out["acls"]) == 1


def test_far_future_group_stays_put() -> None:
    acl = _fixture_acl()
    # Not yet expired: only 10 seconds old
    now = _FAR + 10
    expired = find_expired_groups(acl, now)
    assert not expired
