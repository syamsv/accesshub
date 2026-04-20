"""Authenticated async HTTP client for the Tailscale API.

Mirrors the design of the incidentio Python client: an `attrs`-based
class that lazily builds an `httpx.AsyncClient` and injects the bearer
token on first use.

Only the authenticated variant is provided — the Tailscale API requires
auth for every endpoint. Only async — this client has no sync surface.
"""

import ssl
from typing import Any

import httpx
from attrs import define, evolve, field

TAILSCALE_API_BASE_URL = "https://api.tailscale.com/api/v2"


@define
class AuthenticatedClient:
    """A Tailscale API client with a bearer token.

    Keyword arguments used internally when building `httpx.AsyncClient`:

        ``base_url``: defaults to Tailscale's public API
          (``https://api.tailscale.com/api/v2``)
        ``cookies``, ``headers``, ``timeout``, ``verify_ssl``,
        ``follow_redirects``, ``httpx_args``: see httpx docs.

    Attributes:
        token: The Tailscale API access token (personal or OAuth).
        prefix: Authorization header scheme, default ``"Bearer"``.
        auth_header_name: Header name, default ``"Authorization"``.
        raise_on_unexpected_status: If True, api functions raise
            :class:`errors.UnexpectedStatus` on undocumented responses.
    """

    token: str
    prefix: str = "Bearer"
    auth_header_name: str = "Authorization"

    raise_on_unexpected_status: bool = field(default=False, kw_only=True)
    _base_url: str = field(default=TAILSCALE_API_BASE_URL, kw_only=True, alias="base_url")
    _cookies: dict[str, str] = field(factory=dict, kw_only=True, alias="cookies")
    _headers: dict[str, str] = field(factory=dict, kw_only=True, alias="headers")
    _timeout: httpx.Timeout | None = field(default=None, kw_only=True, alias="timeout")
    _verify_ssl: str | bool | ssl.SSLContext = field(
        default=True, kw_only=True, alias="verify_ssl"
    )
    _follow_redirects: bool = field(default=False, kw_only=True, alias="follow_redirects")
    _httpx_args: dict[str, Any] = field(factory=dict, kw_only=True, alias="httpx_args")
    _async_client: httpx.AsyncClient | None = field(default=None, init=False)

    # ------------------------------------------------------------------ #
    # fluent customizers                                                  #
    # ------------------------------------------------------------------ #

    def with_headers(self, headers: dict[str, str]) -> "AuthenticatedClient":
        if self._async_client is not None:
            self._async_client.headers.update(headers)
        return evolve(self, headers={**self._headers, **headers})

    def with_cookies(self, cookies: dict[str, str]) -> "AuthenticatedClient":
        if self._async_client is not None:
            self._async_client.cookies.update(cookies)
        return evolve(self, cookies={**self._cookies, **cookies})

    def with_timeout(self, timeout: httpx.Timeout) -> "AuthenticatedClient":
        if self._async_client is not None:
            self._async_client.timeout = timeout
        return evolve(self, timeout=timeout)

    # ------------------------------------------------------------------ #
    # async httpx.AsyncClient                                             #
    # ------------------------------------------------------------------ #

    def set_async_httpx_client(self, async_client: httpx.AsyncClient) -> "AuthenticatedClient":
        """Override the underlying `httpx.AsyncClient` — bypasses all other settings."""
        self._async_client = async_client
        return self

    def get_async_httpx_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._headers[self.auth_header_name] = (
                f"{self.prefix} {self.token}" if self.prefix else self.token
            )
            self._async_client = httpx.AsyncClient(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._async_client

    async def __aenter__(self) -> "AuthenticatedClient":
        await self.get_async_httpx_client().__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self.get_async_httpx_client().__aexit__(*args, **kwargs)


__all__ = ["TAILSCALE_API_BASE_URL", "AuthenticatedClient"]
