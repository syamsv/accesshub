import asyncio

import config
from tailscale import AuthenticatedClient
from tailscale.api.devices import list_tailnet_devices
from tailscale.models import ListTailnetDevicesFields


def init():
    config.init(
        env_file=".env",
        required=[
            "TAILNET",
            "TAILSCALE_API_KEY",
        ],
    )


async def list_devices():
    async with AuthenticatedClient(
        token=config.TAILSCALE_API_KEY,
        raise_on_unexpected_status=True,
    ) as client:
        resp = await list_tailnet_devices.asyncio(
            config.TAILNET,
            client=client,
            fields=ListTailnetDevicesFields.DEFAULT,
            tags=["tag:server"],
        )
        if resp is None:
            print("no response body from Tailscale")
            return
        print(resp.devices)
        for d in resp.devices:
            print(f"{d.id:<20} {d.hostname:<30} {d.os:<10} {d.last_seen}")


if __name__ == "__main__":
    init()
    asyncio.run(list_devices())
