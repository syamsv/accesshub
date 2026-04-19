"""Tailscale policy file (ACL) model.

Ref: https://tailscale.com/api#tag/policyfile
"""

from typing import Any, Dict, List, Union

from attrs import define, field

from ..types import UNSET, Unset


@define
class ACL:
    """A tailnet policy file.

    Tailscale's policy file is a flexible document; the most common
    top-level fields are modelled explicitly. Anything Tailscale adds
    later is preserved in ``additional_properties`` so callers can
    still read it via ``acl.additional_properties["new_field"]``.
    """

    acls: Union[Unset, List[Dict[str, Any]]] = UNSET
    groups: Union[Unset, Dict[str, List[str]]] = UNSET
    tag_owners: Union[Unset, Dict[str, List[str]]] = UNSET
    hosts: Union[Unset, Dict[str, str]] = UNSET
    tests: Union[Unset, List[Dict[str, Any]]] = UNSET
    ssh: Union[Unset, List[Dict[str, Any]]] = UNSET
    node_attrs: Union[Unset, List[Dict[str, Any]]] = UNSET
    auto_approvers: Union[Unset, Dict[str, Any]] = UNSET
    derp_map: Union[Unset, Dict[str, Any]] = UNSET
    randomize_client_port: Union[Unset, bool] = UNSET
    disable_ipv4: Union[Unset, bool] = UNSET
    posture: Union[Unset, Dict[str, Any]] = UNSET

    additional_properties: Dict[str, Any] = field(factory=dict)

    # ------------------------------------------------------------------ #
    # (de)serialisation                                                   #
    # ------------------------------------------------------------------ #

    _FIELD_MAP = {
        "tag_owners": "tagOwners",
        "node_attrs": "nodeAttrs",
        "auto_approvers": "autoApprovers",
        "derp_map": "derpMap",
        "randomize_client_port": "randomizeClientPort",
        "disable_ipv4": "disableIPv4",
    }

    _FLAT_FIELDS = ("acls", "groups", "hosts", "tests", "ssh", "posture")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to the JSON shape Tailscale expects (camelCase keys)."""
        out: Dict[str, Any] = dict(self.additional_properties)
        for py_name in self._FLAT_FIELDS:
            value = getattr(self, py_name)
            if not isinstance(value, Unset):
                out[py_name] = value
        for py_name, api_name in self._FIELD_MAP.items():
            value = getattr(self, py_name)
            if not isinstance(value, Unset):
                out[api_name] = value
        return out

    @classmethod
    def from_dict(cls, src: Dict[str, Any]) -> "ACL":
        data = dict(src)
        kwargs: Dict[str, Any] = {}

        for py_name, api_name in cls._FIELD_MAP.items():
            if api_name in data:
                kwargs[py_name] = data.pop(api_name)

        for flat in cls._FLAT_FIELDS:
            if flat in data:
                kwargs[flat] = data.pop(flat)

        instance = cls(**kwargs)
        instance.additional_properties = data
        return instance
