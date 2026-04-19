"""Grant a Tailscale ACL rule for an approved access request.

Called from :func:`slackbot.common._decide` when an admin approves a
request. The flow:

    1. Fetch the current policy file (and its ETag) from Tailscale.
    2. Compose a stable, request-scoped group name:
         group:accesshub-<id>-<epoch>-<duration>
    3. Classify ``req["device"]``:
         - starts with ``tag:`` → destination is ``<tag>:*``.
         - hostname            → resolve to Tailscale IP; destination is
                                 ``<ip>:*``.
    4. Mutate the ACL in-memory: add the group and append the rule.
    5. Validate the proposed policy with Tailscale's validate endpoint.
    6. POST it back with ``If-Match: <etag>`` for optimistic concurrency;
       retry up to three times on ``412 Precondition Failed``.
    7. Persist the grant in SQLite so revocation can find it.

Revocation itself is left to a separate polling job (runs every ~5 min
per the design).
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import config
from assets.tailscale import get_device_ip
from tailscale import AuthenticatedClient, UnexpectedStatus
from tailscale.api.policyfile import (
    get_tailnet_acl,
    set_tailnet_acl,
    validate_tailnet_acl,
)
from tailscale.models import ACL

import db

logger = logging.getLogger(__name__)

_MAX_ETAG_RETRIES = 3


def _group_name(request_id: str, creation_epoch: int, duration_label: str) -> str:
    return f"group:accesshub-{request_id}-{creation_epoch}-{duration_label}"


def _duration_label(duration: str) -> str:
    """Tailscale tag/group names must match ^[a-z0-9-]+$ — 'permanent' stays
    lowercase; numeric minutes pass through."""
    return duration if duration == "permanent" else str(int(duration))


def _expires_at(duration: str) -> Optional[str]:
    if duration == "permanent":
        return None
    return (datetime.now(timezone.utc) + timedelta(minutes=int(duration))).isoformat()


async def _requester_email(slack_client, slack_user_id: str) -> Optional[str]:
    try:
        resp = await slack_client.users_info(user=slack_user_id)
        return resp["user"]["profile"].get("email")
    except Exception as e:
        logger.error("users.info failed for %s: %s", slack_user_id, e)
        return None


def _ensure_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _ensure_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _apply_mutation(
    acl: ACL,
    *,
    email: str,
    group_name: str,
    dst: str,
) -> None:
    """Layer our additions onto a freshly fetched ACL in-place."""
    groups = _ensure_dict(acl.groups)
    groups[group_name] = [email]
    acl.groups = groups

    rules = _ensure_list(acl.acls)
    rules.append({"action": "accept", "src": [group_name], "dst": [dst]})
    acl.acls = rules


async def perform_grant(slack_client, *, request_id: str, req: dict) -> bool:
    """Run the grant workflow. Returns True on success, False otherwise.

    Mutates SQLite via ``db.mark_granted`` on success, ``db.set_grant_state``
    on failure. All non-happy-path branches are logged with the request id
    so operators can correlate with the admin DM.
    """
    await db.set_grant_state(request_id, "granting")

    email = await _requester_email(slack_client, req["user_id"])
    if not email:
        logger.error("[grant %s] no email for requester %s", request_id, req["user_id"])
        await db.set_grant_state(request_id, "failed")
        return False

    device = (req.get("device") or "").strip()
    creation_epoch = int(time.time())
    duration_label = _duration_label(req["duration"])
    group_name = _group_name(request_id, creation_epoch, duration_label)

    # Classify target: tag reference vs hostname
    if device.startswith("tag:"):
        dst = f"{device}:*"
    else:
        ip = get_device_ip(device)
        if not ip:
            logger.error(
                "[grant %s] could not resolve hostname %r to a Tailscale IP",
                request_id, device,
            )
            await db.set_grant_state(request_id, "failed")
            return False
        dst = f"{ip}:*"

    # Read-modify-write with ETag retry
    async with AuthenticatedClient(
        token=config.TAILSCALE_API_KEY, raise_on_unexpected_status=False
    ) as ts:
        for attempt in range(_MAX_ETAG_RETRIES):
            get_resp = await get_tailnet_acl.asyncio_detailed(config.TAILNET, client=ts)
            acl = get_resp.parsed
            if acl is None:
                logger.error("[grant %s] GET /acl failed: %s", request_id, get_resp.status_code)
                await db.set_grant_state(request_id, "failed")
                return False
            etag = get_resp.headers.get("ETag")

            _apply_mutation(
                acl,
                email=email,
                group_name=group_name,
                dst=dst,
            )

            # Validate first — fail early if the policy is malformed.
            validation = await validate_tailnet_acl.asyncio(
                config.TAILNET, client=ts, body=acl
            )
            if validation and validation.get("message"):
                logger.error(
                    "[grant %s] validation failed: %s",
                    request_id, validation.get("message"),
                )
                await db.set_grant_state(request_id, "failed")
                return False

            # Commit
            try:
                set_resp = await set_tailnet_acl.asyncio_detailed(
                    config.TAILNET, client=ts, body=acl, if_match=etag
                )
            except UnexpectedStatus as e:
                logger.error("[grant %s] POST /acl crashed: %s", request_id, e)
                await db.set_grant_state(request_id, "failed")
                return False

            if set_resp.status_code == 200:
                break
            if set_resp.status_code == 412:
                logger.info(
                    "[grant %s] ETag stale, retrying (%d/%d)",
                    request_id, attempt + 1, _MAX_ETAG_RETRIES,
                )
                continue
            logger.error(
                "[grant %s] POST /acl returned %s: %s",
                request_id, set_resp.status_code, set_resp.content[:300],
            )
            await db.set_grant_state(request_id, "failed")
            return False
        else:
            logger.error(
                "[grant %s] gave up after %d ETag retries", request_id, _MAX_ETAG_RETRIES
            )
            await db.set_grant_state(request_id, "failed")
            return False

    await db.mark_granted(
        request_id,
        creation_epoch=creation_epoch,
        expires_at=_expires_at(req["duration"]),
        acl_group_name=group_name,
        acl_tag_name=None,
        acl_dst=dst,
    )
    logger.info(
        "[grant %s] applied: group=%s dst=%s",
        request_id, group_name, dst,
    )
    return True
