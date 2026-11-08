"""Bounded, policy-gated LXC OS/APT probe contract.

The module contains no shell execution and no Proxmox calls.  A future
root-owned discovery transport may implement ``probe`` with fixed argv only.
This separation makes the safe default explicit and keeps malformed guest
output untrusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol


MAX_PROBE_OUTPUT_BYTES = 64 * 1024


class ProbeState(str, Enum):
    PASS = "pass"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"
    STOPPED = "stopped"
    UNAUTHORIZED = "unauthorized"
    PROBE_FAILED = "probe_failed"


@dataclass(frozen=True, slots=True)
class ProbeResult:
    container_id: int
    state: ProbeState
    os_id: str | None = None
    version_id: str | None = None
    apt_version: str | None = None
    dpkg_version: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "container_id": self.container_id,
            "state": self.state.value,
            "os_id": self.os_id,
            "version_id": self.version_id,
            "apt_version": self.apt_version,
            "dpkg_version": self.dpkg_version,
            "error": self.error,
        }


class DiscoveryProbeTransport(Protocol):
    """Fixed-scope transport; it must not accept command text from callers."""

    def probe(self, container_id: int) -> Mapping[str, str]: ...


def _valid_container_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 999_999


def _bounded(value: Any) -> str | None:
    if not isinstance(value, str) or len(value.encode("utf-8", "replace")) > MAX_PROBE_OUTPUT_BYTES:
        return None
    return value


def parse_os_release(text: str) -> tuple[str | None, str | None]:
    """Parse only ID/VERSION_ID from a bounded os-release payload."""

    if _bounded(text) is None:
        raise ValueError("probe output exceeds the configured limit")
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {"ID", "VERSION_ID"}:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value and all(char.isalnum() or char in "._-" for char in value):
                values[key] = value
    return values.get("ID"), values.get("VERSION_ID")


def evaluate_probe(record: Mapping[str, Any], *, transport: DiscoveryProbeTransport | None, discovery_enabled: bool) -> ProbeResult:
    """Evaluate one inventory record without retrying or changing the guest."""

    container_id = record.get("container_id")
    if not _valid_container_id(container_id):
        return ProbeResult(0, ProbeState.PROBE_FAILED, error="invalid-container-id")
    if record.get("running") is not True:
        return ProbeResult(container_id, ProbeState.STOPPED, error="container-is-not-running")
    if not discovery_enabled or transport is None:
        return ProbeResult(container_id, ProbeState.UNAUTHORIZED, error="discovery-probe-not-authorized")
    try:
        payload = transport.probe(container_id)
        os_id, version_id = parse_os_release(payload.get("os_release", ""))
        apt_version = _bounded(payload.get("apt_version"))
        dpkg_version = _bounded(payload.get("dpkg_version"))
    except (KeyError, TypeError, ValueError, OSError, TimeoutError):
        return ProbeResult(container_id, ProbeState.PROBE_FAILED, error="probe-output-invalid-or-unavailable")
    if not os_id or not version_id or not apt_version or not dpkg_version:
        return ProbeResult(container_id, ProbeState.UNKNOWN, os_id, version_id, apt_version, dpkg_version, "required-os-or-apt-evidence-missing")
    if os_id.lower() not in {"debian", "ubuntu"}:
        return ProbeResult(container_id, ProbeState.UNSUPPORTED, os_id, version_id, apt_version, dpkg_version, "operating-system-unsupported")
    return ProbeResult(container_id, ProbeState.PASS, os_id, version_id, apt_version, dpkg_version)
