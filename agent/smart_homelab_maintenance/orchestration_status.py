"""Non-secret status model for agent health and HA display."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import stat
from pathlib import Path
from typing import Any, Callable, Mapping

from .policy import PolicyMode


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
    policy_generation: int = 0
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


def _authorized_ids(entries: Mapping[str, Mapping[str, Any]]) -> list[int]:
    """Normalize legacy and split grants without conflating their meanings."""

    result: list[int] = []
    for raw_id, values in entries.items():
        if not isinstance(raw_id, str) or not raw_id.isdigit():
            raise ValueError("policy container id is invalid")
        container_id = int(raw_id)
        if not 1 <= container_id <= 999_999 or not isinstance(values, Mapping):
            raise ValueError("policy container entry is invalid")
        for key in ("authorized", "simulation_authorized", "update_authorized"):
            if key in values and not isinstance(values[key], bool):
                raise ValueError("policy authorization field is invalid")
        # An explicit split field wins over the legacy field.  update_authorized
        # is deliberately never used as a simulation grant.
        simulation = values["simulation_authorized"] if "simulation_authorized" in values else values.get("authorized", False)
        if simulation is True:
            result.append(container_id)
    return sorted(set(result))


def read_installation_status(
    *,
    policy_reader: Callable[[], Mapping[str, Mapping[str, Any]]] | None = None,
    policy_mode_reader: Callable[[], str] | None = None,
    policy_generation_reader: Callable[[], int] | None = None,
    runtime_status: OrchestrationStatus | None = None,
) -> OrchestrationStatus:
    """Return non-secret installation state without starting or changing anything."""

    helper_files = (HELPER_PATH, DISCOVERY_PATH, HELPER_UNIT_PATH, DISCOVERY_UNIT_PATH)
    helper_installed = all(_root_regular(path) for path in helper_files)
    try:
        socket_active = DISCOVERY_SOCKET_PATH.is_socket()
    except OSError:
        socket_active = False
    policy_ok = False
    security_error: str | None = None
    policy_mode = "discover_only"
    policy_generation = 0
    authorized_ids: list[int] = []
    if policy_reader is not None:
        try:
            entries = policy_reader()
            if not isinstance(entries, Mapping):
                raise ValueError("policy response is not a mapping")
            authorized_ids = _authorized_ids(entries)
            policy_ok = True
        except Exception:
            # Never expose helper/file details through the status endpoint.
            security_error = "policy_unavailable"
    if policy_mode_reader is not None:
        try:
            policy_mode = PolicyMode(policy_mode_reader()).value
        except Exception:
            security_error = "policy_invalid"
            policy_ok = False
    if policy_generation_reader is not None:
        try:
            generation = policy_generation_reader()
            if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
                raise ValueError("invalid generation")
            policy_generation = generation
        except Exception:
            security_error = "policy_invalid"
            policy_ok = False
    current = runtime_status or OrchestrationStatus()
    return OrchestrationStatus(
        helper_installed=helper_installed,
        discovery_socket_active=socket_active,
        integrity_ok=helper_installed and socket_active and policy_ok and security_error is None,
        policy_mode=policy_mode,
        policy_generation=policy_generation,
        last_reconcile_at=current.last_reconcile_at,
        authorized_container_ids=authorized_ids,
        unauthorized_container_ids=list(current.unauthorized_container_ids),
        stale_container_ids=list(current.stale_container_ids),
        security_error=security_error,
        last_apply=current.last_apply,
        rollback_status=current.rollback_status,
    )
