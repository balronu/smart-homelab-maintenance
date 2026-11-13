"""Domain types shared by the offline agent core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping


class InstallKind(StrEnum):
    APT = "apt"
    GIT_SYSTEMD = "git_systemd"
    UV_SYSTEMD = "uv_systemd"
    DOCKER = "docker"
    UNKNOWN = "unknown"


class JobState(StrEnum):
    QUEUED = "queued"
    PREFLIGHT = "preflight"
    WAITING_CONFIRMATION = "waiting_confirmation"
    RUNNING = "running"
    POSTCHECK = "postcheck"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    MANUAL_RECOVERY = "manual_recovery_required"
    CANCELLED = "cancelled"
    RECONCILED_NOT_EXECUTED = "reconciled_not_executed"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    RECOVERY_PENDING = "recovery_pending"
    RECONCILED_COMPLETED = "reconciled_completed"
    RECOVERY_BLOCKED = "recovery_blocked"
    RECONCILED_LEGACY_STATE_VERIFIED = "reconciled_legacy_state_verified"


class JobPhase(StrEnum):
    DISCOVERY = "discovery"
    PREFLIGHT = "preflight"
    EXECUTION = "execution"
    POSTCHECK = "postcheck"
    RECOVERY = "recovery"
    COMPLETE = "complete"


TERMINAL_STATES = frozenset(
    {
        JobState.SUCCEEDED,
        JobState.FAILED,
        JobState.BLOCKED,
        JobState.TIMEOUT,
        JobState.MANUAL_RECOVERY,
        JobState.CANCELLED,
        JobState.RECONCILED_NOT_EXECUTED,
        JobState.COMPLETED,
        JobState.INTERRUPTED,
        JobState.RECONCILED_COMPLETED,
        JobState.RECOVERY_BLOCKED,
    }
)


@dataclass(frozen=True, slots=True)
class ContainerRef:
    container_id: int
    name: str
    running: bool
    os_name: str = "unknown"
    os_version: str = "unknown"
    install_kind: InstallKind = InstallKind.UNKNOWN

    def __post_init__(self) -> None:
        if self.container_id < 1 or self.container_id > 999_999:
            raise ValueError("container_id must be a positive PVE VMID")
        if not self.name or len(self.name) > 128:
            raise ValueError("container name must be between 1 and 128 characters")


@dataclass(frozen=True, slots=True)
class ApplicationRef:
    app_id: str
    display_name: str
    container_id: int
    install_kind: InstallKind
    installed_version: str | None = None
    available_version: str | None = None
    supported: bool = False


@dataclass(frozen=True, slots=True)
class JobRequest:
    target: str
    operation: str
    expected_version: str | None
    idempotency_key: str
    confirmation_hash: str | None = None


@dataclass(frozen=True, slots=True)
class Verification:
    """Evidence that is required before a job can become successful."""

    preflight_passed: bool
    postcheck_passed: bool
    observed_version: str | None = None
    message: str = ""

    @property
    def successful(self) -> bool:
        return self.preflight_passed and self.postcheck_passed


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    free_bytes: int
    total_bytes: int
    memory_available_bytes: int | None = None
    swap_in_use_bytes: int | None = None
    thinpool_percent: float | None = None


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    min_free_bytes: int = 4 * 1024**3
    min_memory_available_bytes: int = 512 * 1024**2
    max_thinpool_percent: float = 90.0
    max_swap_in_use_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
