from slack_bolt.async_app import AsyncApp

from .common import access_request_approve, access_request_deny
from .home import home_app_home_opened
from .tailscale import tailscale_access_command, tailscale_access_command_submit


def Start(
    signing_secret: str,
    token: str,
    port: int = 3000,
):
    app = AsyncApp(
        signing_secret=signing_secret,
        token=token,
    )
    routing(app)
    app.start(port=port)


def routing(app: AsyncApp):
    app.event("app_home_opened")(home_app_home_opened)

    # tailscale
    app.command("/accesshub_tailscale")(tailscale_access_command)
    app.view("tailscale_access")(tailscale_access_command_submit)
    app.action("access_request_approve")(access_request_approve)
    app.action("access_request_deny")(access_request_deny)
