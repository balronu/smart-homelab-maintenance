"""Non-secret status model for agent health and HA display."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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
