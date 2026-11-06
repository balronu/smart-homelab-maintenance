"""Read-only Proxmox inventory adapters and API client.

The network client implements only bounded HTTPS GET requests to the
versioned Proxmox API.  It never invokes a shell and never accepts command
text from API input.  Unknown guest/application metadata remains unknown.
"""

from __future__ import annotations

import ipaddress
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from .errors import MaintenanceError


class ProxmoxClientError(MaintenanceError):
    code = "proxmox_unavailable"


class ProxmoxAuthenticationError(ProxmoxClientError):
    code = "proxmox_authentication"


class ProxmoxTlsError(ProxmoxClientError):
    code = "proxmox_tls"


class ProxmoxResponseError(ProxmoxClientError):
    code = "proxmox_invalid_response"


@dataclass(frozen=True, slots=True)
class ProxmoxClientConfig:
    base_url: str
    node: str
    api_token: str
    ca_file: str | None = None
    timeout: float = 10.0
    max_bytes: int = 512_000

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.base_url.rstrip("/"))
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Proxmox URL must be HTTPS without embedded credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("Proxmox URL must not contain query or fragment")
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            address = None
        private_name = parsed.hostname == "localhost" or parsed.hostname.endswith((".home.arpa", ".lan", ".local"))
        if address is not None and not (address.is_private or address.is_loopback):
            raise ValueError("Proxmox URL must use a private address")
        if address is None and not private_name:
            raise ValueError("Proxmox URL must use a private DNS name")
        if not self.node or "/" in self.node or self.timeout <= 0 or self.max_bytes < 1024:
            raise ValueError("invalid Proxmox client configuration")
        if not self.api_token or any(char.isspace() for char in self.api_token):
            raise ValueError("Proxmox credential is malformed")


class ProxmoxApiClient:
    """Minimal read-only Proxmox JSON API client."""

    def __init__(self, config: ProxmoxClientConfig, *, opener: Callable[..., Any] | None = None) -> None:
        self.config = config
        self._opener = opener or urllib.request.urlopen

    def _context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(cafile=self.config.ca_file)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return context

    def _get(self, path: str) -> Mapping[str, Any]:
        url = self.config.base_url.rstrip("/") + "/" + path.lstrip("/")
        request = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Authorization": "PVEAPIToken " + self.config.api_token,
        }, method="GET")
        try:
            response = self._opener(request, timeout=self.config.timeout, context=self._context())
            with response:
                body = response.read(self.config.max_bytes + 1)
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ProxmoxAuthenticationError("Proxmox authentication failed") from None
            raise ProxmoxClientError("Proxmox API request failed") from None
        except (urllib.error.URLError, TimeoutError, OSError, ssl.SSLError) as exc:
            if isinstance(exc, ssl.SSLError):
                raise ProxmoxTlsError("Proxmox TLS validation failed") from None
            raise ProxmoxClientError("Proxmox API is unavailable") from None
        if status < 200 or status >= 300:
            raise ProxmoxClientError("Proxmox API request failed")
        if len(body) > self.config.max_bytes:
            raise ProxmoxResponseError("Proxmox response exceeds configured limit")
        try:
            payload = json.loads(body.decode("utf-8"))
            data = payload["data"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            raise ProxmoxResponseError("Proxmox returned an invalid response") from None
        if not isinstance(data, (dict, list)):
            raise ProxmoxResponseError("Proxmox returned an invalid response")
        return data  # type: ignore[return-value]

    def node_status(self) -> Mapping[str, Any]:
        raw = self._get(f"nodes/{self.config.node}/status")
        return {
            "name": self.config.node,
            "release": str(raw.get("pveversion", "unknown")),
            "kernel": str(raw.get("kversion", "unknown")),
            "online": raw.get("status") == "online",
        }

    def lxc_list(self) -> list[Mapping[str, Any]]:
        raw = self._get(f"nodes/{self.config.node}/lxc")
        if not isinstance(raw, list):
            raise ProxmoxResponseError("Proxmox returned invalid container data")
        result = []
        for item in raw:
            if not isinstance(item, Mapping) or not isinstance(item.get("vmid"), int):
                continue
            maxmem, mem = item.get("maxmem"), item.get("mem")
            maxdisk, disk = item.get("maxdisk"), item.get("disk")
            result.append({
                "vmid": item["vmid"], "name": item.get("name", f"lxc-{item['vmid']}"),
                "status": item.get("status", "unknown"),
                "memory_available_bytes": maxmem - mem if isinstance(maxmem, int) and isinstance(mem, int) and maxmem >= mem else None,
                "free_bytes": maxdisk - disk if isinstance(maxdisk, int) and isinstance(disk, int) and maxdisk >= disk else None,
                "os_name": "unknown", "os_version": "unknown", "package_manager": None,
                "applications": [],
            })
        return result

    def vm_list(self) -> list[Mapping[str, Any]]:
        raw = self._get(f"nodes/{self.config.node}/qemu")
        if not isinstance(raw, list):
            raise ProxmoxResponseError("Proxmox returned invalid VM data")
        return [{"vmid": item["vmid"], "name": item.get("name", f"vm-{item['vmid']}"),
                 "status": item.get("status", "unknown"), "os_name": "unknown", "os_version": "unknown"}
                for item in raw if isinstance(item, Mapping) and isinstance(item.get("vmid"), int)]


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
