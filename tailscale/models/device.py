"""Tailscale Device model.

Ref: https://tailscale.com/api#tag/devices
"""

from typing import Any, ClassVar

from attrs import define, field

from ..types import UNSET, Unset


@define
class Device:
    """A device enrolled in a tailnet.

    Only `id` is guaranteed to be present in every response. All other
    fields are ``Unset`` when Tailscale did not include them.

    The ``additional_properties`` bag preserves any field added by
    Tailscale after this client was generated, so forward-compatible
    access is possible via ``device.additional_properties["new_field"]``.
    """

    id: str
    node_id: Unset | str = UNSET
    user: Unset | str = UNSET
    name: Unset | str = UNSET
    hostname: Unset | str = UNSET
    client_version: Unset | str = UNSET
    os: Unset | str = UNSET
    addresses: Unset | list[str] = UNSET
    created: Unset | str = UNSET
    last_seen: Unset | str = UNSET
    expires: Unset | str = UNSET
    key_expiry_disabled: Unset | bool = UNSET
    authorized: Unset | bool = UNSET
    is_external: Unset | bool = UNSET
    update_available: Unset | bool = UNSET
    machine_key: Unset | str = UNSET
    node_key: Unset | str = UNSET
    blocks_incoming_connections: Unset | bool = UNSET
    enabled_routes: Unset | list[str] = UNSET
    advertised_routes: Unset | list[str] = UNSET
    tags: Unset | list[str] = UNSET
    client_connectivity: Unset | dict[str, Any] = UNSET
    tailnet_lock_error: Unset | str = UNSET
    tailnet_lock_key: Unset | str = UNSET

    additional_properties: dict[str, Any] = field(factory=dict)

    # ------------------------------------------------------------------ #
    # (de)serialisation                                                   #
    # ------------------------------------------------------------------ #

    _FIELD_MAP: ClassVar[dict[str, str]] = {
        "node_id": "nodeId",
        "client_version": "clientVersion",
        "last_seen": "lastSeen",
        "key_expiry_disabled": "keyExpiryDisabled",
        "is_external": "isExternal",
        "update_available": "updateAvailable",
        "machine_key": "machineKey",
        "node_key": "nodeKey",
        "blocks_incoming_connections": "blocksIncomingConnections",
        "enabled_routes": "enabledRoutes",
        "advertised_routes": "advertisedRoutes",
        "client_connectivity": "clientConnectivity",
        "tailnet_lock_error": "tailnetLockError",
        "tailnet_lock_key": "tailnetLockKey",
    }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON shape Tailscale expects (camelCase keys)."""
        out: dict[str, Any] = dict(self.additional_properties)
        for py_name, api_name in (
            ("id", "id"),
            ("user", "user"),
            ("name", "name"),
            ("hostname", "hostname"),
            ("os", "os"),
            ("addresses", "addresses"),
            ("created", "created"),
            ("expires", "expires"),
            ("authorized", "authorized"),
            ("tags", "tags"),
            *((py, self._FIELD_MAP[py]) for py in self._FIELD_MAP),
        ):
            value = getattr(self, py_name)
            if not isinstance(value, Unset):
                out[api_name] = value
        return out

    @classmethod
    def from_dict(cls, src: dict[str, Any]) -> "Device":
        data = dict(src)
        if "id" not in data or not data["id"]:
            raise ValueError(f"Tailscale Device payload is missing 'id': {src!r}")
        device_id = data.pop("id")

        # camelCase → snake_case for the known mappings
        kwargs: dict[str, Any] = {"id": device_id}
        for py_name, api_name in cls._FIELD_MAP.items():
            if api_name in data:
                kwargs[py_name] = data.pop(api_name)

        # flat-named fields (no rename)
        for flat in (
            "user",
            "name",
            "hostname",
            "os",
            "addresses",
            "created",
            "expires",
            "authorized",
            "tags",
        ):
            if flat in data:
                kwargs[flat] = data.pop(flat)

        instance = cls(**kwargs)
        # anything Tailscale returned that we don't model explicitly
        instance.additional_properties = data
        return instance
