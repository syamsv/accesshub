"""Typed Tailscale API client, modelled on the incidentio Python client.

Only the authenticated flavour is exported — every Tailscale endpoint
requires a bearer token.

Example::

    from tailscale import AuthenticatedClient
    from tailscale.api.devices import list_tailnet_devices
    from tailscale.models import ListTailnetDevicesFields

    client = AuthenticatedClient(token="tskey-api-xxxxx")
    resp = list_tailnet_devices.sync(
        "-",                                    # default tailnet
        client=client,
        fields=ListTailnetDevicesFields.ALL,
    )
    for d in resp.devices:
        print(d.id, d.hostname)
"""

from .client import TAILSCALE_API_BASE_URL, AuthenticatedClient
from .errors import UnexpectedStatus
from .types import UNSET, Response, Unset

__all__ = [
    "TAILSCALE_API_BASE_URL",
    "UNSET",
    "AuthenticatedClient",
    "Response",
    "UnexpectedStatus",
    "Unset",
]
