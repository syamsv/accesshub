_REQUEST_MODEL = {
    "type": "modal",
    "callback_id": "tailscale_access",
    "title": {"type": "plain_text", "text": "Tailscale access", "emoji": True},
    "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
    "close": {"type": "plain_text", "text": "Cancel", "emoji": True},
    "blocks": [
        {
            "type": "input",
            "element": {
                "type": "static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select an item",
                    "emoji": True,
                },
                "options": [],  # add servers here
                "action_id": "access_asset",
            },
            "label": {
                "type": "plain_text",
                "text": "What do you want to access?",
                "emoji": True,
            },
            "optional": True,
        },
        {
            "type": "input",
            "element": {
                "type": "static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select an item",
                    "emoji": True,
                },
                "options": [],  # add values
                "action_id": "access_duration",
            },
            "label": {
                "type": "plain_text",
                "text": "How long do you want to access?",
                "emoji": True,
            },
            "optional": False,
        },
        {
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "access_reason",
            },
            "label": {
                "type": "plain_text",
                "text": "What do you need access for?",
                "emoji": True,
            },
            "optional": True,
        },
    ],
}


_CONFIRMATION_ACCESS = {
    "type": "modal",
    "callback_id": "tailscale_access_confirm",
    "title": {
        "type": "plain_text",
        "text": "Tailscale access confirmation",
        "emoji": True,
    },
    "submit": {"type": "plain_text", "text": "OK", "emoji": True},
    "blocks": [
        {
            "type": "image",
            "title": {
                "type": "plain_text",
                "text": "Your tailscale access request is been forwarded to admin",
                "emoji": True,
            },
            "image_url": "https://storage.googleapis.com/support-forums-api/attachment/thread-254005948-12011634659636208815.png",
            "alt_text": "delicious tacos",
        }
    ],
}


def _fmt(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    if minutes == 1440:
        return "1 day"
    hours, rem = divmod(minutes, 60)
    label = "1 hour" if hours == 1 else f"{hours} hours"
    return label if rem == 0 else f"{label} {rem} min"


def calculateAccessDurationIntervals() -> list[dict]:

    import config

    interval = int(config.ACCESS_DURATION_INTERVAL_IN_MINS)
    options = []
    seen: set[int] = set()

    # interval-based steps up to 24 hours
    minutes = interval
    while minutes <= 1440:
        options.append(
            {
                "text": {"type": "plain_text", "text": _fmt(minutes), "emoji": True},
                "value": str(minutes),
            }
        )
        seen.add(minutes)
        minutes += interval

    # whole-day steps: 1 day … 7 days (skip any already covered by interval steps)
    for days in range(1, 8):
        day_mins = days * 1440
        if day_mins not in seen:
            label = "1 day" if days == 1 else f"{days} days"
            options.append(
                {
                    "text": {"type": "plain_text", "text": label, "emoji": True},
                    "value": str(day_mins),
                }
            )

    # permanent
    options.append(
        {
            "text": {"type": "plain_text", "text": "Permanent", "emoji": True},
            "value": "permanent",
        }
    )

    return options
