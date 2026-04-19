import asyncio
import logging
import time

from slack_sdk.errors import SlackApiError

import config
import db
from assets.tailscale import admin_request_blocks

from . import grant

logger = logging.getLogger(__name__)

# Keep strong refs to fire-and-forget tasks — asyncio only holds weak refs,
# so a task dropped here could be garbage-collected mid-flight.
_background_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def always_confirm(ack):
    await ack()


def _admin_entries() -> list[str]:
    """Parse `ADMIN_SLACK_USER_IDS` (comma-separated) from env.

    Entries may be either Slack user ids (e.g. ``U0123``) or email
    addresses; emails are resolved to ids at send time via
    ``users.lookupByEmail``.
    """
    raw = (config.get("ADMIN_SLACK_USER_IDS", "") or "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()]


# ---------------------------------------------------------------------------
# user-id-by-email cache — same lifetime as grant.resolve_email so admin
# fan-out doesn't hit users.lookupByEmail on every single request dispatch.
# ---------------------------------------------------------------------------

_EMAIL_CACHE_TTL_SECONDS = 300
_email_to_uid_cache: dict[str, tuple[float, str | None]] = {}


async def _resolve_admin(client, value: str) -> str | None:
    """Return a Slack user id; look up by email when value looks like one."""
    if "@" not in value:
        return value
    now = time.monotonic()
    cached = _email_to_uid_cache.get(value)
    if cached and cached[0] > now:
        return cached[1]
    try:
        resp = await client.users_lookupByEmail(email=value)
    except SlackApiError as e:
        logger.error("users.lookupByEmail failed for %s: %s", value, e.response.get("error"))
        return None
    uid = resp["user"]["id"]
    _email_to_uid_cache[value] = (now + _EMAIL_CACHE_TTL_SECONDS, uid)
    return uid


async def resolved_admin_ids(client) -> list[str]:
    """Return the configured admin list with emails resolved to user ids.

    Resolution is concurrent; failed lookups are dropped (logged inside
    ``_resolve_admin``).
    """
    entries = _admin_entries()
    if not entries:
        return []
    results = await asyncio.gather(
        *(_resolve_admin(client, e) for e in entries),
        return_exceptions=True,
    )
    return [r for r in results if isinstance(r, str)]


# ---------------------------------------------------------------------------
# request dispatch
# ---------------------------------------------------------------------------


async def send_access_request_to_admins(
    client,
    *,
    requester_id: str,
    device: str | None,
    duration: str,
    reason: str | None,
) -> str:
    """Persist the request and DM every configured admin (in parallel) with
    approve/deny buttons. Returns the new request id."""
    request_id = await db.create_request(
        user_id=requester_id, device=device, duration=duration, reason=reason
    )

    admin_ids = await resolved_admin_ids(client)
    if not admin_ids:
        logger.warning(
            "no admins configured (ADMIN_SLACK_USER_IDS); request %s has no reviewers",
            request_id,
        )
        return request_id

    blocks = admin_request_blocks(
        request_id=request_id,
        requester_id=requester_id,
        device=device,
        duration=duration,
        reason=reason,
    )
    fallback = f"Access request from <@{requester_id}>"

    async def _send(admin_id: str) -> None:
        try:
            await client.chat_postMessage(channel=admin_id, text=fallback, blocks=blocks)
        except SlackApiError as e:
            logger.error(
                "chat.postMessage to admin %s for request %s: %s",
                admin_id, request_id, e.response.get("error"),
            )

    await asyncio.gather(*(_send(a) for a in admin_ids), return_exceptions=True)
    return request_id


# ---------------------------------------------------------------------------
# approve / deny button handlers
# ---------------------------------------------------------------------------


async def _update_admin_message(client, body: dict, *, request_id: str, decision: str, admin_id: str) -> None:
    """Disable the buttons on the admin's DM so they can't be clicked again."""
    try:
        await client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text=f"Request {decision} by <@{admin_id}>",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Request `{request_id}` *{decision}* by <@{admin_id}>",
                    },
                }
            ],
        )
    except SlackApiError as e:
        logger.error(
            "chat.update for request %s: %s", request_id, e.response.get("error")
        )


async def _decide(ack, body, client, action, decision: str) -> None:
    await ack()
    request_id = action["value"]
    admin_id = body["user"]["id"]

    updated = await db.set_request_decision(
        request_id, status=decision, decided_by=admin_id
    )
    if not updated:
        logger.info(
            "request %s already decided when %s clicked %s",
            request_id, admin_id, decision,
        )
        return

    logger.info("[access] request %s %s by %s", request_id, decision, admin_id)

    # Flip the admin's buttons immediately — latency here matters for UX.
    await _update_admin_message(
        client, body, request_id=request_id, decision=decision, admin_id=admin_id
    )

    req = await db.get_request(request_id)
    if not req:
        logger.error("request %s vanished between decision and dispatch", request_id)
        return

    if decision == "approved":
        # Fire-and-forget: the button handler should not block on the
        # full Tailscale round-trip. The grant module owns its own DB
        # writes and requester DM so the user never sees a bogus
        # "approved" message when the ACL failed to mutate.
        _spawn(
            grant.perform_grant(
                client, request_id=request_id, req=req, admin_id=admin_id
            )
        )
    else:
        # Denied — short-circuit straight to the DM; no ACL work to do.
        await grant.perform_denial_notice(client, req=req, admin_id=admin_id)


async def access_request_approve(ack, body, client, action) -> None:
    await _decide(ack, body, client, action, "approved")


async def access_request_deny(ack, body, client, action) -> None:
    await _decide(ack, body, client, action, "denied")
