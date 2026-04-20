import asyncio
import contextlib
import logging
import signal

import config
import db
import slackbot
from assets.tailscale import warm_services_cache
from cleaner.run import loop as cleaner_loop
from slackbot.grant import reconcile_stuck_grants

logger = logging.getLogger(__name__)


def init() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config.init(
        env_file=".env",
        required=[
            "ACCESS_DURATION_INTERVAL_IN_MINS",
            "TAILNET",
            "TAILSCALE_API_KEY",
            "SLACK_BOT_TOKEN",
            "SLACK_SIGNING_SECRET",
            "ADMIN_SLACK_USER_IDS",
        ],
    )


async def _main() -> None:
    """Run the Slack bot and the ACL cleaner on one event loop.

    Both services share the same ``aiosqlite`` connection and cooperate
    with Tailscale through its ETag-based concurrency, so the bot can
    mutate the policy file while the cleaner is mid-cycle without
    corrupting either side's view.
    """
    # Pre-flight: populate device cache and reconcile any rows left
    # in-flight by a prior crash before we start accepting traffic.
    await warm_services_cache()
    await reconcile_stuck_grants()

    stop_event = asyncio.Event()
    running_loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            running_loop.add_signal_handler(sig, stop_event.set)

    # Start the Bolt HTTP server on *our* event loop.
    runner = await slackbot.start_async(
        signing_secret=config.SLACK_SIGNING_SECRET,
        token=config.SLACK_BOT_TOKEN,
    )

    # Kick the cleaner loop off as a sibling task. It consults
    # ``stop_event`` between ticks so SIGINT/SIGTERM exits it cleanly
    # without cancellation.
    cleaner_task = asyncio.create_task(cleaner_loop(stop_event), name="cleaner")
    logger.info("accesshub ready — bot + cleaner running")

    try:
        await stop_event.wait()
        logger.info("shutdown signal received")
    finally:
        # Cleaner exits on its own once stop_event is set; just await it.
        with contextlib.suppress(asyncio.CancelledError):
            await cleaner_task
        await runner.cleanup()


if __name__ == "__main__":
    init()
    try:
        asyncio.run(_main())
    finally:
        # One last loop to close the shared aiosqlite connection cleanly
        # so WAL checkpoint runs and .db-wal/.db-shm are trimmed.
        with contextlib.suppress(RuntimeError):
            asyncio.run(db.close())
