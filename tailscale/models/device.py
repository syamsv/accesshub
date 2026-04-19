"""Tailscale Device model.

Ref: https://tailscale.com/api#tag/devices
"""

from typing import Any, Dict, List, Union

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
    node_id: Union[Unset, str] = UNSET
    user: Union[Unset, str] = UNSET
    name: Union[Unset, str] = UNSET
    hostname: Union[Unset, str] = UNSET
    client_version: Union[Unset, str] = UNSET
    os: Union[Unset, str] = UNSET
    addresses: Union[Unset, List[str]] = UNSET
    created: Union[Unset, str] = UNSET
    last_seen: Union[Unset, str] = UNSET
    expires: Union[Unset, str] = UNSET
    key_expiry_disabled: Union[Unset, bool] = UNSET
    authorized: Union[Unset, bool] = UNSET
    is_external: Union[Unset, bool] = UNSET
    update_available: Union[Unset, bool] = UNSET
    machine_key: Union[Unset, str] = UNSET
    node_key: Union[Unset, str] = UNSET
    blocks_incoming_connections: Union[Unset, bool] = UNSET
    enabled_routes: Union[Unset, List[str]] = UNSET
    advertised_routes: Union[Unset, List[str]] = UNSET
    tags: Union[Unset, List[str]] = UNSET
    client_connectivity: Union[Unset, Dict[str, Any]] = UNSET
    tailnet_lock_error: Union[Unset, str] = UNSET
    tailnet_lock_key: Union[Unset, str] = UNSET

    additional_properties: Dict[str, Any] = field(factory=dict)

    # ------------------------------------------------------------------ #
    # (de)serialisation                                                   #
    # ------------------------------------------------------------------ #

    _FIELD_MAP = {
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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to the JSON shape Tailscale expects (camelCase keys)."""
        out: Dict[str, Any] = dict(self.additional_properties)
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
    def from_dict(cls, src: Dict[str, Any]) -> "Device":
        data = dict(src)
        device_id = data.pop("id", "")

        # camelCase → snake_case for the known mappings
        kwargs: Dict[str, Any] = {"id": device_id}
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
