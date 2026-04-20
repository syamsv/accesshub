"""`POST /tailnet/{tailnet}/acl/preview` — preview which rules match.

Given a candidate policy file plus either a user email or an
``ip:port`` string, returns the subset of rules that would fire.
Handy for "would this grant actually work?" checks before writing.

Ref: https://tailscale.com/api#tag/policyfile/post/tailnet/{tailnet}/acl/preview
"""

from http import HTTPStatus
from typing import Any, Literal
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient
from ...models.acl import ACL
from ...types import Response

PreviewType = Literal["user", "ipport"]


def _get_kwargs(
    tailnet: str,
    *,
    body: ACL | dict[str, Any],
    type_: PreviewType,
    preview_for: str,
) -> dict[str, Any]:
    payload = body.to_dict() if isinstance(body, ACL) else body
    return {
        "method": "post",
        "url": f"/tailnet/{quote(tailnet, safe='')}/acl/preview",
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        "params": {"type": type_, "previewFor": preview_for},
        "json": payload,
    }


def _parse_response(
    *, client: AuthenticatedClient, response: httpx.Response
) -> dict[str, Any] | None:
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
) -> Response[dict[str, Any]]:
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
    body: ACL | dict[str, Any],
    type_: PreviewType,
    preview_for: str,
) -> Response[dict[str, Any]]:
    """Preview the rules that would match ``preview_for`` under ``body``.

    Args:
        tailnet: Tailnet name, or ``"-"`` for the caller's default tailnet.
        body: The policy file to evaluate (typically the candidate you're
            about to POST).
        type_: ``"user"`` when ``preview_for`` is an email address,
            ``"ipport"`` when it's an ``IP:PORT`` string.
        preview_for: The subject to evaluate against.
    """
    kwargs = _get_kwargs(tailnet, body=body, type_=type_, preview_for=preview_for)
    response = await client.get_async_httpx_client().request(**kwargs)
    return _build_response(client=client, response=response)


async def asyncio(
    tailnet: str,
    *,
    client: AuthenticatedClient,
    body: ACL | dict[str, Any],
    type_: PreviewType,
    preview_for: str,
) -> dict[str, Any] | None:
    """Like :func:`asyncio_detailed` but returns only the parsed body.

    Expected shape (subject to Tailscale API changes)::

        {
          "matches": [ { "action": "accept", "users": [...], "ports": [...], "lineNumber": 3 }, ... ],
          "type": "user",
          "previewFor": "alice@example.com"
        }
    """
    return (
        await asyncio_detailed(
            tailnet, client=client, body=body, type_=type_, preview_for=preview_for
        )
    ).parsed
