"""Non-secret status model for agent health and HA display."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import stat
from pathlib import Path
from typing import Any, Callable, Mapping


HELPER_PATH = Path("/usr/libexec/smart-homelab-maintenance/lxc-apt-helper")
DISCOVERY_PATH = Path("/usr/libexec/smart-homelab-maintenance/lxc-discovery.py")
HELPER_UNIT_PATH = Path("/etc/systemd/system/smart-homelab-maintenance-lxc-helper.service")
DISCOVERY_UNIT_PATH = Path("/etc/systemd/system/smart-homelab-maintenance-lxc-discovery.service")
DISCOVERY_SOCKET_PATH = Path("/run/smart-homelab-maintenance/lxc-discovery.sock")


@dataclass(slots=True)
class OrchestrationStatus:
    helper_installed: bool = False
    discovery_socket_active: bool = False
    helper_version: str | None = None
    helper_commit: str | None = None
    integrity_ok: bool = False
    policy_mode: str = "discover_only"
    last_reconcile_at: str | None = None
    authorized_container_ids: list[int] = field(default_factory=list)
    unauthorized_container_ids: list[int] = field(default_factory=list)
    stale_container_ids: list[int] = field(default_factory=list)
    security_error: str | None = None
    last_apply: dict[str, Any] | None = None
    rollback_status: str = "not_run"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _root_regular(path: Path) -> bool:
    try:
        info = path.stat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and info.st_uid == 0


def read_installation_status(*, policy_reader: Callable[[], Mapping[str, Mapping[str, Any]]] | None = None) -> OrchestrationStatus:
    """Return non-secret installation state without starting or changing anything."""

    helper_files = (HELPER_PATH, DISCOVERY_PATH, HELPER_UNIT_PATH, DISCOVERY_UNIT_PATH)
    helper_installed = all(_root_regular(path) for path in helper_files)
    try:
        socket_active = DISCOVERY_SOCKET_PATH.is_socket()
    except OSError:
        socket_active = False
    policy_ok = False
    security_error: str | None = None
    if policy_reader is not None:
        try:
            policy_ok = isinstance(policy_reader(), Mapping)
        except Exception:
            # Never expose helper/file details through the status endpoint.
            security_error = "policy_unavailable"
    return OrchestrationStatus(
        helper_installed=helper_installed,
        discovery_socket_active=socket_active,
        integrity_ok=helper_installed and socket_active and policy_ok,
        policy_mode="discover_only",
        security_error=security_error,
    )
