"""Read-only Proxmox inventory adapters.

The backend deliberately depends on an injected client.  It does not invoke
shell commands and it never accepts command text from API input.  A production
client can be supplied later after its authentication and permission model is
approved; tests use :class:`FixtureProxmoxClient` only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class ProxmoxReadClient(Protocol):
    def node_status(self) -> Mapping[str, Any]: ...
    def lxc_list(self) -> list[Mapping[str, Any]]: ...
    def vm_list(self) -> list[Mapping[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class FixtureProxmoxClient:
    """Deterministic read-only client used by offline tests."""

    node: Mapping[str, Any]
    lxcs: tuple[Mapping[str, Any], ...] = ()
    vms: tuple[Mapping[str, Any], ...] = ()

    def node_status(self) -> Mapping[str, Any]:
        return dict(self.node)

    def lxc_list(self) -> list[Mapping[str, Any]]:
        return [dict(item) for item in self.lxcs]

    def vm_list(self) -> list[Mapping[str, Any]]:
        return [dict(item) for item in self.vms]


class ProxmoxInventoryBackend:
    """Translate a read-only Proxmox client into discovery records."""

    def __init__(self, client: ProxmoxReadClient) -> None:
        self.client = client

    def host(self) -> dict[str, Any]:
        raw = dict(self.client.node_status())
        return {
            "name": str(raw.get("name", "unknown")),
            "release": str(raw.get("release", "unknown")),
            "kernel": str(raw.get("kernel", "unknown")),
            "online": bool(raw.get("online", True)),
        }

    def containers(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for raw in self.client.lxc_list():
            item = dict(raw)
            vmid = item.get("container_id", item.get("vmid"))
            if not isinstance(vmid, int) or vmid < 1:
                continue
            result.append({
                "container_id": vmid,
                "name": str(item.get("name", f"lxc-{vmid}")),
                "running": item.get("status") == "running" if "status" in item else bool(item.get("running", False)),
                "os_name": str(item.get("os_name", "unknown")),
                "os_version": str(item.get("os_version", "unknown")),
                "memory_available_bytes": item.get("memory_available_bytes"),
                "free_bytes": item.get("free_bytes"),
                "package_manager": item.get("package_manager"),
                "applications": list(item.get("applications", ())),
            })
        return result

    def virtual_machines(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for raw in self.client.vm_list():
            item = dict(raw)
            vmid = item.get("vmid", item.get("container_id"))
            if not isinstance(vmid, int) or vmid < 1:
                continue
            result.append({
                "vmid": vmid,
                "name": str(item.get("name", f"vm-{vmid}")),
                "running": item.get("status") == "running" if "status" in item else bool(item.get("running", False)),
                "os_name": str(item.get("os_name", "unknown")),
                "os_version": str(item.get("os_version", "unknown")),
            })
        return result
