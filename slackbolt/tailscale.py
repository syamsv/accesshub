import logging

logger = logging.getLogger(__name__)


async def tailscale_access_command(ack, body, client):
    await ack()

    user_id = body["user"]["id"]
    try:
        await client.views_open(
            trigger_id=body.get("trigger_id"),
            # view=_REQUEST_MODAL,
        )
        logger.info("tailscale modal invoked by %s", user_id)
    except Exception as e:
        logger.error("Failed to open modal for %s: %s", user_id, e)


async def tailscale_access_command_submit(ack, body):
    values = body["view"]["state"]["values"]
    device = values["device"]["device_input"]["value"]
    duration = values["duration"]["duration_select"]["selected_option"]["value"]
    reason = values["reason"]["reason_input"]["value"]
    user_id = body["user"]["id"]

    logger.info(
        "tailscale access request: user=%s device=%s duration=%s reason=%s",
        user_id,
        device,
        duration,
        reason,
    )

    await ack(
        response_action="update",
        # view=_CONFIRM_VIEW,
    )
