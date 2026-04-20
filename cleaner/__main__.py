"""Entrypoint for ``python -m cleaner``.

Runs the cleanup daemon as a standalone process. Shares the SQLite file
with the Slack bot (WAL mode makes concurrent reads/writes safe) and
coordinates with the bot's grant path through Tailscale's own ETag.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

import config
import db

from .run import loop


def _init() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config.init(
        env_file=".env",
        required=[
            "TAILNET",
            "TAILSCALE_API_KEY",
        ],
    )


async def _main() -> None:
    stop = asyncio.Event()
    loop_ref = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop_ref.add_signal_handler(sig, stop.set)
    await loop(stop)


if __name__ == "__main__":
    _init()
    try:
        asyncio.run(_main())
    finally:
        with contextlib.suppress(RuntimeError):
            asyncio.run(db.close())
