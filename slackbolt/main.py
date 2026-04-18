from slack_bolt.async_app import AsyncApp


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
    pass
