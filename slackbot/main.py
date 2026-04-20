import logging

from aiohttp import web
from slack_bolt.adapter.aiohttp import to_aiohttp_response, to_bolt_request
from slack_bolt.async_app import AsyncApp

from .common import access_request_approve, access_request_deny
from .home import home_app_home_opened
from .tailscale import tailscale_access_command, tailscale_access_command_submit

logger = logging.getLogger(__name__)


def _build_app(signing_secret: str, token: str) -> AsyncApp:
    app = AsyncApp(signing_secret=signing_secret, token=token)
    routing(app)
    return app


def Start(signing_secret: str, token: str, port: int = 3000) -> None:
    """Synchronous entrypoint. Blocks on aiohttp's own event loop.

    Kept for backwards compatibility; prefer :func:`start_async` so the
    bot shares the event loop with the cleaner daemon.
    """
    _build_app(signing_secret, token).start(port=port)


async def start_async(
    signing_secret: str,
    token: str,
    *,
    host: str = "0.0.0.0",
    port: int = 3000,
    path: str = "/slack/events",
) -> web.AppRunner:
    """Start the Bolt HTTP server on the **current** event loop and return
    the :class:`aiohttp.web.AppRunner` so the caller can cleanly shut it
    down later.

    Implemented on top of ``slack_bolt.adapter.aiohttp`` and the aiohttp
    ``AppRunner`` / ``TCPSite`` pattern, not ``AsyncApp.start()`` — that
    one calls ``web.run_app()`` which creates its own event loop and
    blocks, preventing any sibling coroutines from sharing the loop.
    """
    bolt_app = _build_app(signing_secret, token)

    async def _events_handler(request: web.Request) -> web.Response:
        bolt_req = await to_bolt_request(request)
        bolt_resp = await bolt_app.async_dispatch(bolt_req)
        return await to_aiohttp_response(bolt_resp)

    web_app = web.Application()
    web_app.router.add_post(path, _events_handler)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    logger.info("Bolt listening on http://%s:%d%s", host, port, path)
    return runner


def routing(app: AsyncApp) -> None:
    app.event("app_home_opened")(home_app_home_opened)

    # tailscale
    app.command("/accesshub_tailscale")(tailscale_access_command)
    app.view("tailscale_access")(tailscale_access_command_submit)
    app.action("access_request_approve")(access_request_approve)
    app.action("access_request_deny")(access_request_deny)
