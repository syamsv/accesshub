import logging

from slack_sdk.errors import SlackApiError

from assets.home import _APP_HOME_OPENED

logger = logging.getLogger(__name__)


async def home_app_home_opened(event, client):
    if event.get("tab") != "home":
        return
    try:
        await client.views_publish(user_id=event["user"], view=_APP_HOME_OPENED)
    except SlackApiError as e:
        logger.error(
            "views.publish for %s: %s", event.get("user"), e.response.get("error")
        )
