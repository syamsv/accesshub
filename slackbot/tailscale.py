import logging

from assets.tailscale import _CONFIRMATION_ACCESS, getRequestModal

from .common import send_access_request_to_admins

logger = logging.getLogger(__name__)


async def tailscale_access_command(ack, body, client):
    await ack()

    user_id = body.get("user_id")
    try:
        await client.views_open(
            trigger_id=body.get("trigger_id"),
            view=await getRequestModal(),
        )
        logger.info("tailscale modal invoked by %s", user_id)
    except Exception as e:
        logger.error("Failed to open modal for %s: %s", user_id, e)


async def tailscale_access_command_submit(ack, body, client):
    await ack(
        response_action="update",
        view=_CONFIRMATION_ACCESS,
    )

    values = body["view"]["state"]["values"]
    device_sel = values["device"]["access_asset"].get("selected_option")
    device = device_sel["value"] if device_sel else None
    duration = values["duration"]["access_duration"]["selected_option"]["value"]
    reason = values["reason"]["access_reason"].get("value")
    user_id = body["user"]["id"]

    logger.info(
        "tailscale access request: user=%s device=%s duration=%s reason=%s",
        user_id,
        device,
        duration,
        reason,
    )

    try:
        request_id = await send_access_request_to_admins(
            client,
            requester_id=user_id,
            device=device,
            duration=duration,
            reason=reason,
        )
        logger.info("dispatched access request %s to admins", request_id)
    except Exception as e:
        logger.error("failed to dispatch access request for %s: %s", user_id, e)
