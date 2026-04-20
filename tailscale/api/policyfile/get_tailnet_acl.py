"""`GET /tailnet/{tailnet}/acl` — fetch a tailnet's policy file.

Ref: https://tailscale.com/api#tag/policyfile/get/tailnet/{tailnet}/acl
"""

from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient
from ...models.acl import ACL
from ...types import Response


def _get_kwargs(tailnet: str) -> dict[str, Any]:
    # `tailnet` can be "-" (the default tailnet) or a full name like "example.com".
    # Request JSON explicitly — Tailscale serves HuJSON by default for this endpoint.
    return {
        "method": "get",
        "url": f"/tailnet/{quote(tailnet, safe='')}/acl",
        "headers": {"Accept": "application/json"},
    }


def _parse_response(
    *, client: AuthenticatedClient, response: httpx.Response
) -> ACL | None:
    if response.status_code == 200:
        return ACL.from_dict(response.json())
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    return None


def _build_response(
    *, client: AuthenticatedClient, response: httpx.Response
) -> Response[ACL]:
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
) -> Response[ACL]:
    """Fetch the tailnet policy file, returning the full `Response` wrapper.

    Args:
        tailnet: Tailnet name, or ``"-"`` for the caller's default tailnet.

    Raises:
        errors.UnexpectedStatus: on undocumented status codes when
            ``client.raise_on_unexpected_status`` is True.
        httpx.TimeoutException: if the request exceeds the client's timeout.
    """
    kwargs = _get_kwargs(tailnet)
    response = await client.get_async_httpx_client().request(**kwargs)
    return _build_response(client=client, response=response)


async def asyncio(
    tailnet: str,
    *,
    client: AuthenticatedClient,
) -> ACL | None:
    """Like :func:`asyncio_detailed` but returns only the parsed body."""
    return (await asyncio_detailed(tailnet, client=client)).parsed
