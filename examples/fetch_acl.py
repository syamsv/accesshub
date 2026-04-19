import asyncio

import config
from tailscale import AuthenticatedClient
from tailscale.api.policyfile import get_tailnet_acl


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
        acl = await get_tailnet_acl.asyncio(config.TAILNET, client=client)
        print(acl)


if __name__ == "__main__":
    init()
    asyncio.run(list_devices())
