"""Async orchestration for the accesshub-ACL cleanup daemon.

Intended to run as its own process (``python -m cleaner``):

* every ``CLEANER_INTERVAL_SECONDS`` (default 300) we fetch the tailnet
  policy file, identify expired ``group:accesshub-…`` groups, and POST
  a mutation that removes both the group and any rules referencing it;
* SQLite rows for each cleaned group flip to ``revoked`` so the bot's
  UI stays in sync;
* ETag-based optimistic concurrency keeps the cleaner safe against
  concurrent grants from the Slack bot — on 412 we simply re-fetch,
  re-apply, re-POST.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

import config
import db
from tailscale import AuthenticatedClient, UnexpectedStatus
from tailscale.api.policyfile import (
    get_tailnet_acl,
    set_tailnet_acl,
    validate_tailnet_acl,
)

from .expiry import ParsedName, apply_cleanup, find_expired_groups

logger = logging.getLogger(__name__)

_MAX_ETAG_RETRIES = 3
_DEFAULT_INTERVAL_SECONDS = 300


def _interval_seconds() -> int:
    raw = config.get("CLEANER_INTERVAL_SECONDS", str(_DEFAULT_INTERVAL_SECONDS))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "CLEANER_INTERVAL_SECONDS=%r is not an int, defaulting to %d",
            raw, _DEFAULT_INTERVAL_SECONDS,
        )
        return _DEFAULT_INTERVAL_SECONDS
    if value <= 0:
        logger.warning(
            "CLEANER_INTERVAL_SECONDS=%d must be positive, defaulting to %d",
            value, _DEFAULT_INTERVAL_SECONDS,
        )
        return _DEFAULT_INTERVAL_SECONDS
    return value


async def _mark_revoked_in_db(expired: list[ParsedName]) -> None:
    """Best-effort: flip each expired group's SQLite row to 'revoked'.

    If the row doesn't exist (e.g. someone crafted the group by hand),
    the UPDATE is a no-op — this is intentional.
    """
    for parsed in expired:
        try:
            await db.mark_revoked(str(parsed.request_id))
        except Exception:
            logger.exception(
                "[cleaner] could not mark request %s revoked", parsed.request_id
            )


async def run_once() -> int:
    """Run one cleanup cycle. Returns the number of groups removed.

    Any exception in a single cycle is logged but not raised — the
    outer :func:`loop` is resilient to transient failures.
    """
    now_epoch = int(time.time())
    async with AuthenticatedClient(
        token=config.TAILSCALE_API_KEY, raise_on_unexpected_status=False
    ) as ts:
        for attempt in range(_MAX_ETAG_RETRIES):
            try:
                get_resp = await get_tailnet_acl.asyncio_detailed(
                    config.TAILNET, client=ts
                )
            except httpx.HTTPError as e:
                logger.error("[cleaner] GET /acl: %s", e)
                return 0

            acl = get_resp.parsed
            if acl is None:
                logger.error(
                    "[cleaner] GET /acl returned %s", get_resp.status_code
                )
                return 0
            etag = get_resp.headers.get("ETag")
            if not etag:
                logger.error(
                    "[cleaner] Tailscale response missing ETag — refusing unsafe POST"
                )
                return 0

            expired = find_expired_groups(acl, now_epoch)
            if not expired:
                logger.debug("[cleaner] nothing to remove")
                return 0

            logger.info(
                "[cleaner] removing %d expired group(s): %s",
                len(expired), [p.name for p in expired],
            )

            apply_cleanup(acl, expired)

            validation = await validate_tailnet_acl.asyncio(
                config.TAILNET, client=ts, body=acl
            )
            if validation and validation.get("message"):
                logger.error(
                    "[cleaner] validate rejected cleanup: %s",
                    validation.get("message"),
                )
                return 0

            try:
                set_resp = await set_tailnet_acl.asyncio_detailed(
                    config.TAILNET, client=ts, body=acl, if_match=etag
                )
            except (httpx.HTTPError, UnexpectedStatus) as e:
                logger.error("[cleaner] POST /acl: %s", e)
                return 0

            if set_resp.status_code == 200:
                await _mark_revoked_in_db(expired)
                return len(expired)
            if set_resp.status_code == 412:
                logger.info(
                    "[cleaner] ETag stale, retrying (%d/%d)",
                    attempt + 1, _MAX_ETAG_RETRIES,
                )
                continue
            logger.error(
                "[cleaner] POST /acl returned %s: %s",
                set_resp.status_code, set_resp.content[:200],
            )
            return 0

        logger.error(
            "[cleaner] gave up after %d ETag retries", _MAX_ETAG_RETRIES
        )
        return 0


async def loop(stop_event: asyncio.Event | None = None) -> None:
    """Run :func:`run_once` forever on the configured interval.

    Pass ``stop_event`` (set it from a signal handler) to break out of
    the loop cleanly; otherwise the task runs until cancelled.
    """
    interval = _interval_seconds()
    logger.info("[cleaner] starting; interval=%ds", interval)
    stop_event = stop_event or asyncio.Event()

    while not stop_event.is_set():
        try:
            removed = await run_once()
            if removed:
                logger.info("[cleaner] cycle removed %d group(s)", removed)
        except Exception:
            logger.exception("[cleaner] unhandled exception in cycle")

        # asyncio.wait_for with a short-circuit event gives us a
        # cancellable sleep — a SIGTERM can end the loop within seconds
        # instead of waiting the full interval.
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue
    logger.info("[cleaner] stop requested, exiting loop")
