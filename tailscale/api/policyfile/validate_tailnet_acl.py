"""`POST /tailnet/{tailnet}/acl/validate` — dry-run a policy file.

Validates a proposed policy file and runs any embedded ``tests`` without
persisting. Useful before calling :mod:`set_tailnet_acl` so malformed
rules never reach the live policy.

Ref: https://tailscale.com/api#tag/policyfile/post/tailnet/{tailnet}/acl/validate
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
) -> Dict[str, Any]:
    payload = body.to_dict() if isinstance(body, ACL) else body
    return {
        "method": "post",
        "url": f"/tailnet/{quote(tailnet, safe='')}/acl/validate",
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        "json": payload,
    }


def _parse_response(
    *, client: AuthenticatedClient, response: httpx.Response
) -> Optional[Dict[str, Any]]:
    """Tailscale returns 200 for both success and validation failure.

    Success: empty body (or ``{}``).
    Failure: ``{"message": "...", "data": [...]}`` with details.
    Callers should check whether the returned dict has a ``message`` key
    to decide if validation passed.
    """
    if response.status_code == 200:
        try:
            return response.json() or {}
        except ValueError:
            return {}
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    return None


def _build_response(
    *, client: AuthenticatedClient, response: httpx.Response
) -> Response[Dict[str, Any]]:
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
) -> Response[Dict[str, Any]]:
    """Validate a proposed policy file and run its embedded tests."""
    kwargs = _get_kwargs(tailnet, body=body)
    response = await client.get_async_httpx_client().request(**kwargs)
    return _build_response(client=client, response=response)


async def asyncio(
    tailnet: str,
    *,
    client: AuthenticatedClient,
    body: Union[ACL, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Like :func:`asyncio_detailed` but returns only the parsed body.

    An empty dict (``{}``) means the policy validated cleanly. A dict
    with a ``"message"`` key means Tailscale rejected it — inspect
    ``data`` for per-rule details.
    """
    return (await asyncio_detailed(tailnet, client=client, body=body)).parsed
