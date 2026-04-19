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


"""
when a request is approved the following workflow happens ,
1 - current acl gets fetched (stores to some place - later to be added )
2 - addes a group with custom name `group:accesshub-<REQUEST_ID>-<CREATION_TIME>-<DURATION_in_MINUTES>`
3 - check if the user is asking for a tag or a machine
    3.1 - if machine a tag is created with `tag:accesshub-<REQUEST_ID>-<CREATION_TIME>-<DURATION_in_MINUTES>`
    3.2 - tailscale_ip:* as dst
    3.3 - tag gets stored
4 - acl rule is added with gtoup ans tag to access lke below (validate)
5 - validates the time befiore commiting as we will be deploying a seperate funcition that edits the acl every 5 min for removal



"acls": [

	{
		"action": "accept",
		"src":    [group:accesshub-<REQUEST_ID>-<CREATION_TIME>-<DURATION_in_MINUTES>],
		"dst":    [anything],
	},
]
"""

if __name__ == "__main__":
    init()
    asyncio.run(warm_services_cache())
    slackbot.Start(
        signing_secret=config.SLACK_SIGNING_SECRET,
        token=config.SLACK_BOT_TOKEN,
    )
