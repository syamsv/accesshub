"""`POST /tailnet/{tailnet}/acl` — replace the tailnet's policy file.

Ref: https://tailscale.com/api#tag/policyfile/post/tailnet/{tailnet}/acl
"""

from http import HTTPStatus
from typing import Any, Dict, Optional, Union
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient
from ...models.acl import ACL
from ...types import Response


def _get_kwargs(
    tailnet: str,
    *,
    body: Union[ACL, Dict[str, Any]],
    if_match: Optional[str] = None,
) -> Dict[str, Any]:
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if if_match is not None:
        headers["If-Match"] = if_match

    payload = body.to_dict() if isinstance(body, ACL) else body

    return {
        "method": "post",
        "url": f"/tailnet/{quote(tailnet, safe='')}/acl",
        "headers": headers,
        "json": payload,
    }


def _parse_response(
    *, client: AuthenticatedClient, response: httpx.Response
) -> Optional[ACL]:
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
    body: Union[ACL, Dict[str, Any]],
    if_match: Optional[str] = None,
) -> Response[ACL]:
    """Replace the policy file.

    Args:
        tailnet: Tailnet name, or ``"-"`` for the caller's default tailnet.
        body: The full policy file to set. Accepts an :class:`ACL` or a
            plain dict (already in camelCase API shape).
        if_match: Optional ETag (from a prior GET) for optimistic
            concurrency. Tailscale returns ``412 Precondition Failed``
            when the ETag no longer matches — re-GET and retry.

    Raises:
        errors.UnexpectedStatus: on undocumented status codes when
            ``client.raise_on_unexpected_status`` is True.
    """
    kwargs = _get_kwargs(tailnet, body=body, if_match=if_match)
    response = await client.get_async_httpx_client().request(**kwargs)
    return _build_response(client=client, response=response)


async def asyncio(
    tailnet: str,
    *,
    client: AuthenticatedClient,
    body: Union[ACL, Dict[str, Any]],
    if_match: Optional[str] = None,
) -> Optional[ACL]:
    """Like :func:`asyncio_detailed` but returns only the parsed body."""
    return (
        await asyncio_detailed(tailnet, client=client, body=body, if_match=if_match)
    ).parsed
