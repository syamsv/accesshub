import asyncio
import copy
import time

import config
from tailscale import UNSET, AuthenticatedClient
from tailscale.api.devices import list_tailnet_devices
from tailscale.models import ListTailnetDevicesFields

from .home import _APP_ERROR

_SERVICES_TTL_SECONDS = 60
_services_cache: tuple[float, list[dict]] | None = None  # (expires_at, options)
_services_refresh_lock = asyncio.Lock()

# Populated as a side-effect of _fetch_access_services so the grant flow can
# resolve the chosen hostname to a Tailscale IP without a second API call.
_device_ip_by_host: dict[str, str] = {}


def get_device_ip(hostname: str) -> str | None:
    """Return the cached Tailscale IP for a hostname, or None if unknown."""
    return _device_ip_by_host.get(hostname)


def _get_resource_tags() -> list[str]:
    """Parse `TAILSCALE_RESOURCE_TAGS` (comma-separated) from env.

    Tolerates surrounding quotes and an inline ``# comment`` that the
    simple .env loader leaves in place.
    """
    raw = config.get("TAILSCALE_RESOURCE_TAGS", "") or ""
    if "#" in raw:
        raw = raw.split("#", 1)[0]
    raw = raw.strip().strip('"').strip("'")
    return [t.strip() for t in raw.split(",") if t.strip()]


_REQUEST_MODEL = {
    "type": "modal",
    "callback_id": "tailscale_access",
    "title": {"type": "plain_text", "text": "Tailscale access", "emoji": True},
    "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
    "close": {"type": "plain_text", "text": "Cancel", "emoji": True},
    "blocks": [
        {
            "type": "input",
            "block_id": "device",
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
            "block_id": "duration",
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
            "block_id": "reason",
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
        "text": "Access requested",
        "emoji": True,
    },
    "close": {"type": "plain_text", "text": "Close", "emoji": True},
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":white_check_mark: Your Tailscale access request has been forwarded to the admin.",
            },
        }
    ],
}


def admin_request_blocks(
    *,
    request_id: str,
    requester_id: str,
    device: str | None,
    duration: str,
    reason: str | None,
) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Access request* from <@{requester_id}>",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Device/Tag:*\n{device or '—'}"},
                {"type": "mrkdwn", "text": f"*Duration:*\n{format_duration(duration)}"},
                {"type": "mrkdwn", "text": f"*Reason:*\n{reason or '—'}"},
            ],
        },
        {
            "type": "actions",
            "block_id": "access_decision",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "action_id": "access_request_approve",
                    "value": request_id,
                },
                {
                    "type": "button",
                    "style": "danger",
                    "text": {"type": "plain_text", "text": "Deny"},
                    "action_id": "access_request_deny",
                    "value": request_id,
                },
            ],
        },
    ]


def format_duration(value: str | int | None) -> str:
    """Render the stored duration ("60", "240", "permanent") as human text."""
    if value is None or value == "":
        return "—"
    if isinstance(value, str) and value.lower() == "permanent":
        return "Permanent"
    try:
        return _fmt(int(value))
    except (TypeError, ValueError):
        return str(value)


def _fmt(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    if minutes == 1440:
        return "1 day"
    hours, rem = divmod(minutes, 60)
    label = "1 hour" if hours == 1 else f"{hours} hours"
    return label if rem == 0 else f"{label} {rem} min"


def calculateAccessDurationIntervals() -> list[dict]:
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


async def _fetch_access_services() -> list[dict]:
    options: list[dict] = []
    async with AuthenticatedClient(
        token=config.TAILSCALE_API_KEY, raise_on_unexpected_status=True
    ) as client:
        tags = _get_resource_tags()
        resp = await list_tailnet_devices.asyncio(
            config.TAILNET,
            client=client,
            fields=ListTailnetDevicesFields.DEFAULT,
            tags=tags if tags else UNSET,
        )
        if resp is None:
            print("no response body from Tailscale")
            return options
        print(f"tailscale: {len(resp.devices)} device(s) matched tags={tags or 'ANY'}")

        seen: set[str] = set()

        def add(value: str) -> None:
            if not value or value in seen:
                return
            seen.add(value)
            options.append(
                {
                    "text": {"type": "plain_text", "text": value, "emoji": True},
                    "value": value,
                }
            )

        for d in resp.devices:
            if isinstance(d.hostname, str):
                add(d.hostname)
                if isinstance(d.addresses, list) and d.addresses:
                    _device_ip_by_host[d.hostname] = d.addresses[0]
            if isinstance(d.tags, list):
                for tag in d.tags:
                    add(tag)

    return options


async def _refresh_services_cache() -> None:
    """Fetch fresh data and update the cache. Swallows errors so callers never block on a failed refresh."""
    global _services_cache
    if _services_refresh_lock.locked():
        return  # another refresh is already running
    async with _services_refresh_lock:
        try:
            options = await _fetch_access_services()
            _services_cache = (time.monotonic() + _SERVICES_TTL_SECONDS, options)
        except Exception as e:
            print(f"tailscale: cache refresh failed: {e}")


async def warm_services_cache() -> None:
    """Blocking warm-up — call once at startup so the first slash command is instant."""
    global _services_cache
    async with _services_refresh_lock:
        try:
            options = await _fetch_access_services()
            _services_cache = (time.monotonic() + _SERVICES_TTL_SECONDS, options)
        except Exception as e:
            print(f"tailscale: cache warm-up failed: {e}")


async def getAccessServicesList() -> list[dict]:
    """Return the device/tag options, serving from cache when possible.

    Cold cache: blocks on the Tailscale API. Warm cache: returns instantly.
    Stale cache: returns the stale entry immediately and refreshes in the
    background so the next call sees fresh data without paying the latency.
    """
    global _services_cache
    now = time.monotonic()

    if _services_cache is None:
        async with _services_refresh_lock:
            if _services_cache is None:  # re-check after acquiring lock
                try:
                    options = await _fetch_access_services()
                    _services_cache = (now + _SERVICES_TTL_SECONDS, options)
                except Exception as e:
                    print(f"tailscale: initial fetch failed: {e}")
                    return []
    elif _services_cache[0] <= now:
        asyncio.create_task(_refresh_services_cache())

    return list(_services_cache[1]) if _services_cache else []


async def getRequestModal() -> dict:
    """Return `_REQUEST_MODEL` populated, or `_APP_ERROR` if Tailscale had no matches."""
    services = await getAccessServicesList()
    if not services:
        return copy.deepcopy(_APP_ERROR)

    modal = copy.deepcopy(_REQUEST_MODEL)
    durations = calculateAccessDurationIntervals()

    for block in modal["blocks"]:
        element = block.get("element", {})
        action_id = element.get("action_id")
        if action_id == "access_asset":
            element["options"] = services
        elif action_id == "access_duration":
            element["options"] = durations

    return modal
