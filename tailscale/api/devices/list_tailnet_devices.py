"""`GET /tailnet/{tailnet}/devices` — list every device in a tailnet.

Ref: https://tailscale.com/api#tag/devices/get/tailnet/{tailnet}/devices
"""

from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient
from ...models.list_tailnet_devices_fields import ListTailnetDevicesFields
from ...models.list_tailnet_devices_response import ListTailnetDevicesResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    tailnet: str,
    *,
    fields: Unset | ListTailnetDevicesFields = UNSET,
    tags: Unset | list[str] | str = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    if not isinstance(fields, Unset):
        params["fields"] = fields.value if isinstance(fields, ListTailnetDevicesFields) else fields

    if not isinstance(tags, Unset):
        # accept a List[str] or a pre-joined comma-separated string
        params["tags"] = ",".join(tags) if isinstance(tags, list) else tags

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    # `tailnet` can be "-" (the default tailnet) or a full name like "example.com"
    return {
        "method": "get",
        "url": f"/tailnet/{quote(tailnet, safe='')}/devices",
        "params": params,
    }


def _parse_response(
    *, client: AuthenticatedClient, response: httpx.Response
) -> ListTailnetDevicesResponse | None:
    if response.status_code == 200:
        return ListTailnetDevicesResponse.from_dict(response.json())
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    return None


def _build_response(
    *, client: AuthenticatedClient, response: httpx.Response
) -> Response[ListTailnetDevicesResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


async def asyncio_detailed(
    tailnet: str,
    *,
    client: AuthenticatedClient,
    fields: Unset | ListTailnetDevicesFields = UNSET,
    tags: Unset | list[str] | str = UNSET,
) -> Response[ListTailnetDevicesResponse]:
    """List every device in `tailnet`, returning the full `Response` wrapper.

    Args:
        tailnet: Tailnet name, or ``"-"`` for the caller's default tailnet.
        fields: ``ListTailnetDevicesFields.ALL`` to include
            `clientConnectivity`, otherwise defaults.
        tags: Optional tag filter. Accepts either a list (e.g.
            ``["tag:prod", "tag:web"]``) or a pre-joined comma-separated
            string.

    Raises:
        errors.UnexpectedStatus: on undocumented status codes when
            ``client.raise_on_unexpected_status`` is True.
        httpx.TimeoutException: if the request exceeds the client's timeout.
    """
    kwargs = _get_kwargs(tailnet, fields=fields, tags=tags)
    response = await client.get_async_httpx_client().request(**kwargs)
    return _build_response(client=client, response=response)


async def asyncio(
    tailnet: str,
    *,
    client: AuthenticatedClient,
    fields: Unset | ListTailnetDevicesFields = UNSET,
    tags: Unset | list[str] | str = UNSET,
) -> ListTailnetDevicesResponse | None:
    """Like :func:`asyncio_detailed` but returns only the parsed body."""
    return (
        await asyncio_detailed(tailnet, client=client, fields=fields, tags=tags)
    ).parsed
