"""Grant a Tailscale ACL rule for an approved access request.

Called from :func:`slackbot.common._decide` (as a fire-and-forget task)
when an admin approves a request. The flow:

    1. Resolve the requester's email (via Slack users.info).
    2. Fetch the current policy file and its ETag from Tailscale.
    3. Validate the proposed policy once up front; mutation is
       deterministic across retries so we don't revalidate per attempt.
    4. POST it back with ``If-Match: <etag>`` for optimistic concurrency.
       On 412 we re-GET, re-apply, re-POST — up to three attempts.
    5. Persist the grant in SQLite so revocation can find it.
    6. DM the requester (and, on failure, every admin) with the outcome.
       Keeping the user notification *inside* the grant keeps the DM
       text honest: we never tell the user "approved" when the ACL was
       not actually mutated.

Revocation itself is left to a separate polling job (~5 min cadence).
"""

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from slack_sdk.errors import SlackApiError

import config
import db
from assets.tailscale import format_duration, get_device_ip
from tailscale import AuthenticatedClient, UnexpectedStatus
from tailscale.api.policyfile import (
    get_tailnet_acl,
    set_tailnet_acl,
    validate_tailnet_acl,
)
from tailscale.models import ACL

logger = logging.getLogger(__name__)

_MAX_ETAG_RETRIES = 3


def _group_name(request_id: str, creation_epoch: int, duration_label: str) -> str:
    return f"group:accesshub-{request_id}-{creation_epoch}-{duration_label}"


def _duration_label(duration: str) -> str:
    """Tailscale tag/group names must match ^[a-z0-9-]+$ — 'permanent'
    stays lowercase; numeric minutes pass through."""
    return duration if duration == "permanent" else str(int(duration))


def _expires_at(duration: str) -> str | None:
    if duration == "permanent":
        return None
    return (datetime.now(UTC) + timedelta(minutes=int(duration))).isoformat()


# ---------------------------------------------------------------------------
# user-profile cache — Slack profiles rarely change; a 5-min TTL saves one
# RTT per grant (and a lot more per request-dispatch).
# ---------------------------------------------------------------------------

_USER_CACHE_TTL_SECONDS = 300
_user_email_cache: dict[str, tuple[float, str | None]] = {}


async def resolve_email(slack_client, slack_user_id: str) -> str | None:
    now = time.monotonic()
    cached = _user_email_cache.get(slack_user_id)
    if cached and cached[0] > now:
        return cached[1]
    try:
        resp = await slack_client.users_info(user=slack_user_id)
    except SlackApiError as e:
        logger.error("users.info failed for %s: %s", slack_user_id, e.response.get("error"))
        return None
    email = resp["user"]["profile"].get("email")
    _user_email_cache[slack_user_id] = (now + _USER_CACHE_TTL_SECONDS, email)
    return email


# ---------------------------------------------------------------------------
# ACL mutation
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# DM helpers (kept here so grant-state and DM stay in sync)
# ---------------------------------------------------------------------------


def _outcome_blocks(*, decision: str, admin_id: str, req: dict) -> list[dict]:
    emoji = ":white_check_mark:" if decision == "approved" else ":x:"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{emoji} Your Tailscale access request was "
                    f"*{decision}* by <@{admin_id}>."
                ),
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Device/Tag:*\n{req.get('device') or '—'}"},
                {"type": "mrkdwn", "text": f"*Duration:*\n{format_duration(req.get('duration'))}"},
                {"type": "mrkdwn", "text": f"*Reason:*\n{req.get('reason') or '—'}"},
            ],
        },
    ]


def _failure_blocks(req: dict) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    ":warning: Your Tailscale access request could not be "
                    "fulfilled automatically. An admin has been notified "
                    "and will follow up."
                ),
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Device/Tag:*\n{req.get('device') or '—'}"},
                {"type": "mrkdwn", "text": f"*Duration:*\n{format_duration(req.get('duration'))}"},
                {"type": "mrkdwn", "text": f"*Reason:*\n{req.get('reason') or '—'}"},
            ],
        },
    ]


async def _dm(slack_client, channel: str, text: str, blocks: list[dict]) -> None:
    try:
        await slack_client.chat_postMessage(channel=channel, text=text, blocks=blocks)
    except SlackApiError as e:
        logger.error("DM to %s failed: %s", channel, e.response.get("error"))


async def _notify_requester(
    slack_client, *, req: dict, decision: str, admin_id: str, succeeded: bool
) -> None:
    if succeeded:
        await _dm(
            slack_client,
            req["user_id"],
            f"Your access request was {decision}",
            _outcome_blocks(decision=decision, admin_id=admin_id, req=req),
        )
    else:
        await _dm(
            slack_client,
            req["user_id"],
            "Your access request could not be fulfilled",
            _failure_blocks(req),
        )


async def _notify_admins_of_failure(slack_client, *, request_id: str, reason: str) -> None:
    """Fan a grant-failure notice out to every configured admin in parallel."""
    # Import here to avoid circular import with .common
    from .common import resolved_admin_ids

    admin_ids = await resolved_admin_ids(slack_client)
    if not admin_ids:
        return
    text = f":rotating_light: Grant failed for request `{request_id}` — {reason}"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]

    await asyncio.gather(
        *(_dm(slack_client, a, text, blocks) for a in admin_ids),
        return_exceptions=True,
    )


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------


async def _run_grant(
    slack_client, *, request_id: str, req: dict, admin_id: str
) -> tuple[bool, str]:
    """Return (succeeded, failure_reason). ``failure_reason`` is an empty
    string on success."""
    email = await resolve_email(slack_client, req["user_id"])
    if not email:
        return False, "could not resolve requester's email"

    device = (req.get("device") or "").strip()
    creation_epoch = int(time.time())
    duration_label = _duration_label(req["duration"])
    group_name = _group_name(request_id, creation_epoch, duration_label)

    if device.startswith("tag:"):
        dst = f"{device}:*"
    else:
        ip = get_device_ip(device)
        if not ip:
            return False, f"could not resolve hostname {device!r} to a Tailscale IP"
        dst = f"{ip}:*"

    async with AuthenticatedClient(
        token=config.TAILSCALE_API_KEY, raise_on_unexpected_status=False
    ) as ts:
        # Initial GET + validate once.
        try:
            get_resp = await get_tailnet_acl.asyncio_detailed(config.TAILNET, client=ts)
        except httpx.HTTPError as e:
            return False, f"Tailscale GET /acl: {e}"

        acl = get_resp.parsed
        if acl is None:
            return False, f"GET /acl returned {get_resp.status_code}"
        etag = get_resp.headers.get("ETag")
        if not etag:
            return False, "Tailscale response missing ETag — refusing unsafe POST"

        _apply_mutation(acl, email=email, group_name=group_name, dst=dst)

        validation = await validate_tailnet_acl.asyncio(config.TAILNET, client=ts, body=acl)
        if validation and validation.get("message"):
            return False, f"validation: {validation.get('message')}"

        # POST + ETag retry. Mutation is deterministic, so on 412 we simply
        # re-GET and re-apply; no need to re-validate.
        for attempt in range(_MAX_ETAG_RETRIES):
            try:
                set_resp = await set_tailnet_acl.asyncio_detailed(
                    config.TAILNET, client=ts, body=acl, if_match=etag
                )
            except (httpx.HTTPError, UnexpectedStatus) as e:
                return False, f"Tailscale POST /acl: {e}"

            if set_resp.status_code == 200:
                break
            if set_resp.status_code == 412:
                logger.info(
                    "[grant %s] ETag stale, retrying (%d/%d)",
                    request_id, attempt + 1, _MAX_ETAG_RETRIES,
                )
                try:
                    get_resp = await get_tailnet_acl.asyncio_detailed(config.TAILNET, client=ts)
                except httpx.HTTPError as e:
                    return False, f"Tailscale GET /acl on retry: {e}"
                acl = get_resp.parsed
                if acl is None:
                    return False, f"GET /acl on retry returned {get_resp.status_code}"
                etag = get_resp.headers.get("ETag")
                if not etag:
                    return False, "Tailscale response missing ETag on retry"
                _apply_mutation(acl, email=email, group_name=group_name, dst=dst)
                continue
            return False, f"POST /acl returned {set_resp.status_code}: {set_resp.content[:200]!r}"
        else:
            return False, f"gave up after {_MAX_ETAG_RETRIES} ETag retries"

    await db.mark_granted(
        request_id,
        creation_epoch=creation_epoch,
        expires_at=_expires_at(req["duration"]),
        acl_group_name=group_name,
        acl_dst=dst,
    )
    logger.info("[grant %s] applied: group=%s dst=%s", request_id, group_name, dst)
    return True, ""


async def perform_grant(slack_client, *, request_id: str, req: dict, admin_id: str) -> bool:
    """Full grant pipeline. Marks DB state, applies the ACL mutation, DMs
    the requester, and on failure DMs admins. Intended to run as a
    fire-and-forget ``asyncio.create_task`` from the button handler.

    Returns True on success, False on failure. Callers typically don't
    need the return value — state is in SQLite and DMs are in Slack.
    """
    await db.set_grant_state(request_id, "granting")
    try:
        ok, reason = await _run_grant(
            slack_client, request_id=request_id, req=req, admin_id=admin_id
        )
    except Exception:
        # Unexpected programmer error — log with traceback so it's not silent.
        logger.exception("[grant %s] unhandled exception", request_id)
        ok, reason = False, "internal error (see logs)"

    if not ok:
        logger.error("[grant %s] FAILED: %s", request_id, reason)
        await db.set_grant_state(request_id, "failed")

    fresh = await db.get_request(request_id) or req
    await _notify_requester(
        slack_client,
        req=fresh,
        decision="approved",
        admin_id=admin_id,
        succeeded=ok,
    )
    if not ok:
        await _notify_admins_of_failure(
            slack_client, request_id=request_id, reason=reason
        )
    return ok


async def perform_denial_notice(slack_client, *, req: dict, admin_id: str) -> None:
    """DM the requester that their request was denied. Parallel to
    :func:`perform_grant` for the happy-denial path."""
    await _notify_requester(
        slack_client, req=req, decision="denied", admin_id=admin_id, succeeded=True
    )


async def reconcile_stuck_grants() -> None:
    """Scan on startup for rows caught mid-grant or mid-revoke by a crash.

    We don't auto-retry the Tailscale mutation — an orphaned ACL rule
    vs a never-applied one look identical in the DB and we can't tell
    them apart without a (potentially expensive) ACL probe. Instead:

    - mark every ``granting``/``revoking`` row ``failed``
    - log each one loudly so an operator can inspect the live ACL and
      clean up by hand.

    Caller: ``main.py``, after ``warm_services_cache`` and before
    ``slackbot.Start`` so we see the log lines before traffic starts.
    """
    stuck = await db.list_stuck_grants()
    if not stuck:
        return
    for row in stuck:
        logger.warning(
            "[reconcile] request %s was mid-%s at startup "
            "(group=%s dst=%s) — check Tailscale ACL manually",
            row["id"], row.get("grant_state"),
            row.get("acl_group_name"), row.get("acl_dst"),
        )
        await db.set_grant_state(str(row["id"]), "failed")
