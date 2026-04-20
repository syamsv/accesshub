"""Pure parsing + expiry logic for accesshub-owned groups.

No Tailscale or DB I/O — just functions over names and ACL dicts, so
the rules are trivially unit-testable.

Group names written by :mod:`slackbot.grant` have the shape::

    group:accesshub-<request_id>-<creation_epoch>-<duration>

where ``<duration>`` is either numeric minutes or the literal
``permanent``. Anything that doesn't match is left alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from tailscale.models import ACL

_NAME_RE = re.compile(r"^group:accesshub-(\d+)-(\d+)-(\d+|permanent)$")


@dataclass(frozen=True)
class ParsedName:
    name: str
    request_id: int
    creation_epoch: int
    duration_label: str  # "<minutes>" or "permanent"

    @property
    def is_permanent(self) -> bool:
        return self.duration_label == "permanent"

    @property
    def expires_at_epoch(self) -> int | None:
        if self.is_permanent:
            return None
        return self.creation_epoch + int(self.duration_label) * 60


def parse_name(name: str) -> ParsedName | None:
    """Return a :class:`ParsedName` if ``name`` is accesshub-owned, else None."""
    m = _NAME_RE.match(name)
    if not m:
        return None
    return ParsedName(
        name=name,
        request_id=int(m.group(1)),
        creation_epoch=int(m.group(2)),
        duration_label=m.group(3),
    )


def is_expired(parsed: ParsedName, now_epoch: int) -> bool:
    if parsed.is_permanent:
        return False
    assert parsed.expires_at_epoch is not None
    return parsed.expires_at_epoch <= now_epoch


def _ensure_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _ensure_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _rule_belongs_to_expired(rule: Any, expired_names: set[str]) -> bool:
    """True only if the rule is exactly one of ours referencing an expired group.

    Conservative by design: only removes rules where ``src`` is a single
    expired accesshub group. A multi-src rule that happens to mention an
    expired group *and* something else stays put — we'd rather leak a
    narrow rule than delete someone else's work.
    """
    if not isinstance(rule, dict):
        return False
    src = rule.get("src")
    if not isinstance(src, list) or len(src) != 1:
        return False
    return src[0] in expired_names


def find_expired_groups(acl: ACL, now_epoch: int) -> list[ParsedName]:
    """Return every accesshub-owned group in ``acl`` whose expiry has passed."""
    out: list[ParsedName] = []
    for name in _ensure_dict(acl.groups):
        parsed = parse_name(name)
        if parsed and is_expired(parsed, now_epoch):
            out.append(parsed)
    return out


def apply_cleanup(acl: ACL, expired: list[ParsedName]) -> None:
    """Remove expired groups and the rules referencing them, in place."""
    if not expired:
        return
    expired_set = {p.name for p in expired}
    acl.groups = {
        k: v
        for k, v in _ensure_dict(acl.groups).items()
        if k not in expired_set
    }
    acl.acls = [
        r
        for r in _ensure_list(acl.acls)
        if not _rule_belongs_to_expired(r, expired_set)
    ]
