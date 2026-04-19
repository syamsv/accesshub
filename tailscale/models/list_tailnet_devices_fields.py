from enum import Enum


class ListTailnetDevicesFields(str, Enum):
    """Value for the `fields` query param on `GET /tailnet/{tailnet}/devices`.

    - ``DEFAULT`` — the common fields (default if not specified)
    - ``ALL`` — every field Tailscale exposes, including expensive ones
      such as `clientConnectivity`
    """

    DEFAULT = "default"
    ALL = "all"

    def __str__(self) -> str:
        return self.value
