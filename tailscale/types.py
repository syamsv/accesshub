"""Shared types for the Tailscale client."""

from http import HTTPStatus
from typing import Any, Generic, Optional, TypeVar

from attrs import define

T = TypeVar("T")


class Unset:
    """Sentinel for unset query / body values.

    An `Unset` value is serialized as "not sent" — this is distinct from `None`
    which Tailscale treats as an explicit null.
    """

    _singleton: Optional["Unset"] = None

    def __new__(cls) -> "Unset":
        if cls._singleton is None:
            cls._singleton = super().__new__(cls)
        return cls._singleton

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Unset = Unset()


@define
class Response(Generic[T]):
    """The raw HTTP response paired with the parsed body (if any)."""

    status_code: HTTPStatus
    content: bytes
    headers: Any
    parsed: T | None


__all__ = ["UNSET", "Response", "Unset"]
