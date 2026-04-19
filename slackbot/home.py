import logging

from assets.home import _APP_HOME_OPENED

logger = logging.getLogger(__name__)


async def home_app_home_opened(event, client):
    try:
        if event.get("tab") != "home":
            return
        await client.views_publish(user_id=event["user"], view=_APP_HOME_OPENED)
    except Exception as e:
        logger.error("Failed to publish app home for %s: %s", event.get("user"), e)
