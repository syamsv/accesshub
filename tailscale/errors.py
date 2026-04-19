"""Errors raised by the Tailscale client."""


class UnexpectedStatus(Exception):
    """Raised by api functions when the response has a status code not documented in the Tailscale API spec."""

    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content
        super().__init__(
            f"Unexpected status code: {status_code}\n\nResponse content:\n{content.decode(errors='ignore')}"
        )


__all__ = ["UnexpectedStatus"]
