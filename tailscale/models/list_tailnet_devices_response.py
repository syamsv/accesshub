"""Response body of `GET /tailnet/{tailnet}/devices`."""

from typing import Any

from attrs import define, field

from .device import Device


@define
class ListTailnetDevicesResponse:
    """Wraps the `{ "devices": [ … ] }` response returned by Tailscale."""

    devices: list[Device] = field(factory=list)
    additional_properties: dict[str, Any] = field(factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = dict(self.additional_properties)
        out["devices"] = [d.to_dict() for d in self.devices]
        return out

    @classmethod
    def from_dict(cls, src: dict[str, Any]) -> "ListTailnetDevicesResponse":
        data = dict(src)
        raw_devices = data.pop("devices", []) or []
        instance = cls(devices=[Device.from_dict(d) for d in raw_devices])
        instance.additional_properties = data
        return instance
