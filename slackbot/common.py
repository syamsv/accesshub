import logging

import config
import db
from assets.tailscale import admin_request_blocks, format_duration

logger = logging.getLogger(__name__)


async def always_confirm(ack):
    await ack()


def _admin_ids() -> list[str]:
    """Parse `ADMIN_SLACK_USER_IDS` (comma-separated) from env.

    Entries may be either Slack user ids (e.g. ``U0123``) or email
    addresses; emails are resolved to ids at send time via
    ``users.lookupByEmail``.
    """
    raw = config.get("ADMIN_SLACK_USER_IDS", "") or ""
    if "#" in raw:
        raw = raw.split("#", 1)[0]
    raw = raw.strip().strip('"').strip("'")
    return [x.strip() for x in raw.split(",") if x.strip()]


async def _resolve_admin(client, value: str) -> str | None:
    """Return a Slack user id; look up by email when `value` looks like one."""
    if "@" not in value:
        return value
    try:
        resp = await client.users_lookupByEmail(email=value)
        return resp["user"]["id"]
    except Exception as e:
        logger.error("failed to resolve admin email %s: %s", value, e)
        return None


async def send_access_request_to_admins(
    client,
    *,
    requester_id: str,
    device: str | None,
    duration: str,
    reason: str | None,
) -> str:
    """Persist the request, DM every configured admin with approve/deny buttons.

    Returns the new request id (Mongo ObjectId as string).
    """
    request_id = await db.create_request(
        user_id=requester_id, device=device, duration=duration, reason=reason
    )

    admins = _admin_ids()
    if not admins:
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

    for admin in admins:
        admin_id = await _resolve_admin(client, admin)
        if not admin_id:
            continue
        try:
            await client.chat_postMessage(
                channel=admin_id, text=fallback, blocks=blocks
            )
        except Exception as e:
            logger.error(
                "failed to DM admin %s for request %s: %s", admin_id, request_id, e
            )

    return request_id


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
            request_id,
            admin_id,
            decision,
        )
        return

    # TODO: trigger the real grant/revoke here. For now just log to stdout.
    print(f"[access] request {request_id} {decision} by {admin_id}")

    # Notify the original requester via DM.
    req = await db.get_request(request_id)
    if req:
        try:
            await client.chat_postMessage(
                channel=req["user_id"],
                text=f"Your access request was {decision}",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "Your Tailscale access request was "
                                f"*{decision}* by <@{admin_id}>."
                            ),
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Device/Tag:*\n{req.get('device') or '—'}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Duration:*\n{format_duration(req.get('duration'))}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Reason:*\n{req.get('reason') or '—'}",
                            },
                        ],
                    },
                ],
            )
        except Exception as e:
            logger.error(
                "failed to notify requester %s for %s: %s",
                req.get("user_id"),
                request_id,
                e,
            )

    # Disable the buttons on the admin's DM so they can't be clicked again.
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
                        "text": (
                            f"Request `{request_id}` *{decision}* by <@{admin_id}>"
                        ),
                    },
                }
            ],
        )
    except Exception as e:
        logger.error("failed to update admin message for %s: %s", request_id, e)


async def access_request_approve(ack, body, client, action) -> None:
    await _decide(ack, body, client, action, "approved")


async def access_request_deny(ack, body, client, action) -> None:
    await _decide(ack, body, client, action, "denied")
