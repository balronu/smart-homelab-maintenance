"""Policy-driven, read-only planning for the LXC helper allowlist.

This module deliberately does not discover guests by running commands in them
and does not write an allowlist.  It converts the current Proxmox inventory
and already-proven guest metadata into a deterministic plan.  A separate,
explicitly authorized installer may apply that plan later.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class AuthorizationMode(str, Enum):
    DISCOVER_ONLY = "discover_only"
    AUTO_AUTHORIZE_SUPPORTED_RUNNING = "auto_authorize_supported_running"


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    container_id: int
    name: str
    running: bool
    os_name: str
    os_version: str
    package_manager: str | None
    authorized: bool
    reason: str


@dataclass(frozen=True, slots=True)
class AllowlistPlan:
    mode: AuthorizationMode
    entries: tuple[AuthorizationDecision, ...]
    authorized_ids: frozenset[int]
    removed_ids: frozenset[int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "authorized_ids": sorted(self.authorized_ids),
            "removed_ids": sorted(self.removed_ids),
            "entries": [
                {
                    "container_id": entry.container_id,
                    "name": entry.name,
                    "running": entry.running,
                    "os_name": entry.os_name,
                    "os_version": entry.os_version,
                    "package_manager": entry.package_manager,
                    "authorized": entry.authorized,
                    "reason": entry.reason,
                }
                for entry in self.entries
            ],
        }


def _valid_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 999_999


def _supported(record: Mapping[str, Any]) -> tuple[bool, str]:
    if not _valid_id(record.get("container_id")):
        return False, "invalid-container-id"
    if record.get("running") is not True:
        return False, "container-stopped"
    os_name = str(record.get("os_name", "")).strip().lower()
    if os_name not in {"debian", "ubuntu"}:
        return False, "operating-system-unsupported-or-unknown"
    if not str(record.get("os_version", "")).strip():
        return False, "operating-system-version-unknown"
    if record.get("package_manager") != "apt":
        return False, "package-manager-unsupported-or-unknown"
    return True, "supported-running-apt"


def plan_allowlist(
    records: Iterable[Mapping[str, Any]],
    *,
    mode: AuthorizationMode = AuthorizationMode.DISCOVER_ONLY,
    existing_authorized_ids: Iterable[int] = (),
    manual_authorized_ids: Iterable[int] = (),
) -> AllowlistPlan:
    """Plan exact numeric entries without granting permissions implicitly.

    ``discover_only`` never adds an ID.  In auto mode only currently running,
    positively identified Debian/Ubuntu APT containers are candidates.  VMs
    cannot enter this function's output because records without a valid
    ``container_id`` are rejected and callers must pass LXC records only.
    Existing IDs not present in the current inventory are reported for
    removal; no file or service is changed here.
    """

    existing = {item for item in existing_authorized_ids if _valid_id(item)}
    manual = {item for item in manual_authorized_ids if _valid_id(item)}
    normalized: list[AuthorizationDecision] = []
    seen: set[int] = set()
    for raw in records:
        container_id = raw.get("container_id")
        if not _valid_id(container_id) or container_id in seen:
            continue
        seen.add(container_id)
        ok, reason = _supported(raw)
        allowed = (mode == AuthorizationMode.AUTO_AUTHORIZE_SUPPORTED_RUNNING and ok) or (container_id in manual and ok)
        # A previously authorized target remains authorized only while the
        # selected policy still permits it.  Stopped/removed/unknown targets
        # therefore cannot retain guest access by stale inventory.
        if mode == AuthorizationMode.DISCOVER_ONLY:
            allowed = container_id in existing and ok
            if container_id in manual and ok:
                allowed = True
            reason = "already-authorized-policy-preserved" if allowed else reason
        normalized.append(AuthorizationDecision(
            container_id=container_id,
            name=str(raw.get("name", f"lxc-{container_id}")),
            running=raw.get("running") is True,
            os_name=str(raw.get("os_name", "unknown")),
            os_version=str(raw.get("os_version", "unknown")),
            package_manager=raw.get("package_manager") if isinstance(raw.get("package_manager"), str) else None,
            authorized=allowed,
            reason=reason,
        ))
    authorized = frozenset(entry.container_id for entry in normalized if entry.authorized)
    return AllowlistPlan(
        mode=mode,
        entries=tuple(sorted(normalized, key=lambda entry: entry.container_id)),
        authorized_ids=authorized,
        # A present-but-stopped/unsupported target must be removed just like
        # a missing target; retaining it would leave stale guest access.
        removed_ids=frozenset(existing - authorized),
    )


def render_allowlist(plan: AllowlistPlan) -> str:
    """Render a deterministic root-owned allowlist candidate.

    The caller must apply ownership, mode and atomic replacement separately.
    """

    lines = [
        "# Generated candidate; apply only through the authorized installer.",
        "# No wildcard or VM entries are valid.",
        "",
    ]
    for entry in plan.entries:
        if not entry.authorized:
            continue
        lines.extend([
            f'[containers."{entry.container_id}"]',
            "authorized = true",
            f'os_name = {entry.os_name!r}',
            f'os_version = {entry.os_version!r}',
            f'package_manager = {entry.package_manager!r}',
            "",
        ])
    return "\n".join(lines)
