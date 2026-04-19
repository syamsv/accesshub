"""Unit tests for the ACL mutation applied on approve.

These exercise the pure-function core of the grant pipeline without any
network, Slack, or DB dependencies.
"""

import pytest

from slackbot.grant import _apply_mutation, _duration_label, _expires_at, _group_name
from tailscale.models import ACL


def _fresh_acl() -> ACL:
    return ACL.from_dict(
        {
            "acls": [{"action": "accept", "src": ["*"], "dst": ["*:*"]}],
            "groups": {"group:existing": ["x@y.com"]},
        }
    )


def test_apply_mutation_hostname_path() -> None:
    acl = _fresh_acl()
    _apply_mutation(
        acl,
        email="alice@example.com",
        group_name="group:accesshub-42-1745000000-60",
        dst="100.64.0.5:*",
    )
    out = acl.to_dict()

    assert out["groups"]["group:accesshub-42-1745000000-60"] == ["alice@example.com"]
    assert out["groups"]["group:existing"] == ["x@y.com"]  # pre-existing preserved
    assert {
        "action": "accept",
        "src": ["group:accesshub-42-1745000000-60"],
        "dst": ["100.64.0.5:*"],
    } in out["acls"]
    # We intentionally do not touch tagOwners.
    assert "tagOwners" not in out


def test_apply_mutation_tag_reference_path() -> None:
    acl = ACL.from_dict({"acls": [], "groups": {}})
    _apply_mutation(
        acl,
        email="bob@example.com",
        group_name="group:accesshub-43-1745000001-30",
        dst="tag:server:*",
    )
    out = acl.to_dict()

    assert out["groups"]["group:accesshub-43-1745000001-30"] == ["bob@example.com"]
    assert out["acls"][-1] == {
        "action": "accept",
        "src": ["group:accesshub-43-1745000001-30"],
        "dst": ["tag:server:*"],
    }
    assert "tagOwners" not in out


def test_group_name_permanent() -> None:
    name = _group_name("7", 1745000000, _duration_label("permanent"))
    assert name == "group:accesshub-7-1745000000-permanent"


def test_group_name_numeric() -> None:
    name = _group_name("7", 1745000000, _duration_label("240"))
    assert name == "group:accesshub-7-1745000000-240"


def test_expires_at_permanent_is_none() -> None:
    assert _expires_at("permanent") is None


def test_expires_at_numeric_is_iso() -> None:
    out = _expires_at("60")
    assert out is not None
    # ISO-8601 with timezone offset, rough shape check.
    assert "T" in out and ("+" in out or out.endswith("Z") or "-" in out[10:])


def test_apply_mutation_idempotent_for_groups() -> None:
    """Two mutations with the same group_name should overwrite, not duplicate."""
    acl = ACL.from_dict({"acls": [], "groups": {}})
    _apply_mutation(
        acl,
        email="a@b.com",
        group_name="group:accesshub-1-1-60",
        dst="100.64.0.5:*",
    )
    _apply_mutation(
        acl,
        email="c@d.com",
        group_name="group:accesshub-1-1-60",
        dst="100.64.0.5:*",
    )
    out = acl.to_dict()
    # Group overwritten (single value, latest wins)
    assert out["groups"]["group:accesshub-1-1-60"] == ["c@d.com"]
    # Rule list appended twice (caller's responsibility to avoid this;
    # test exists to document the behaviour).
    assert len([r for r in out["acls"] if r["src"] == ["group:accesshub-1-1-60"]]) == 2


def test_tag_tags_query_parses_resource_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """_get_resource_tags should handle the cleaned env value from the new loader."""
    import config
    from assets.tailscale import _get_resource_tags

    config.init(env_file=None, required=[])
    monkeypatch.setenv("TAILSCALE_RESOURCE_TAGS", "tag:prod, tag:web , ")
    assert _get_resource_tags() == ["tag:prod", "tag:web"]
    monkeypatch.setenv("TAILSCALE_RESOURCE_TAGS", "")
    assert _get_resource_tags() == []
