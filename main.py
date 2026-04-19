import asyncio
import logging

import config
import slackbot
from assets.tailscale import warm_services_cache


def init():
    logging.basicConfig(level=logging.INFO)
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


if __name__ == "__main__":
    init()
    asyncio.run(warm_services_cache())
    slackbot.Start(
        signing_secret=config.SLACK_SIGNING_SECRET,
        token=config.SLACK_BOT_TOKEN,
    )
