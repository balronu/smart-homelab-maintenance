"""Fixed-scope discovery transport contract.

No socket or subprocess is opened here.  The concrete root-owned service is a
separate deployment concern; this module makes its request/argv contract
testable without granting a shell or a simulation path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

DISCOVERY_SOCKET = "/run/smart-homelab-maintenance/lxc-discovery.sock"
DISCOVERY_OPERATION = "probe"
DISCOVERY_MAX_OUTPUT_BYTES = 64 * 1024
DISCOVERY_TIMEOUT_SECONDS = 10

# Each command is fixed.  A concrete helper must execute these separately and
# return only labelled output; callers cannot supply paths or arguments.
PROBE_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("/usr/bin/cat", "/etc/os-release"),
    ("/usr/bin/apt-get", "--version"),
    ("/usr/bin/dpkg-query", "--version"),
    ("/usr/bin/test", "-x", "/usr/bin/apt-get"),
    ("/usr/bin/test", "-x", "/usr/bin/dpkg-query"),
)


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    container_id: int
    operation: str = DISCOVERY_OPERATION

    def as_dict(self) -> dict[str, Any]:
        return {"container_id": self.container_id, "operation": self.operation}


def build_request(container_id: int) -> DiscoveryRequest:
    if isinstance(container_id, bool) or not isinstance(container_id, int) or not 1 <= container_id <= 999_999:
        raise ValueError("container_id must be a numeric LXC ID")
    return DiscoveryRequest(container_id)


def validate_response(response: Mapping[str, Any], *, container_id: int) -> dict[str, str]:
    """Accept only bounded labelled probe output for the requested LXC."""

    if response.get("ok") is not True or response.get("container_id") != container_id or response.get("operation") != DISCOVERY_OPERATION:
        raise ValueError("discovery response identity or status is invalid")
    result = response.get("result")
    if not isinstance(result, Mapping):
        raise ValueError("discovery response result is invalid")
    allowed = {"os_release", "apt_version", "dpkg_version", "apt_exists", "dpkg_exists"}
    if set(result) != allowed or any(not isinstance(value, str) for value in result.values()):
        raise ValueError("discovery response fields are invalid")
    if sum(len(value.encode("utf-8", "replace")) for value in result.values()) > DISCOVERY_MAX_OUTPUT_BYTES:
        raise ValueError("discovery response exceeds the output limit")
    return {key: str(result[key]) for key in allowed}
