"""One bounded inventory-to-status orchestration pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .apply_controller import AllowlistApplyController, ApplyResult
from .discovery_probe import DiscoveryProbeTransport
from .orchestration_status import OrchestrationStatus
from .policy import Policy
from .reconcile import ReconcileResult, reconcile


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    reconcile: ReconcileResult
    apply: ApplyResult
    status: OrchestrationStatus

    def as_dict(self) -> dict[str, Any]:
        return {"reconcile": self.reconcile.as_dict(), "apply": self.apply.as_dict(), "status": self.status.as_dict()}


class LxcOrchestrator:
    """Connect planning and optional apply without background retries."""

    def __init__(self, controller: AllowlistApplyController, status: OrchestrationStatus | None = None) -> None:
        self.controller = controller
        self.status = status or OrchestrationStatus()

    def run(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        policy: Policy,
        transport: DiscoveryProbeTransport | None,
        existing_authorized_ids: set[int] | frozenset[int] = frozenset(),
        confirmed: bool = False,
    ) -> OrchestrationResult:
        result = reconcile(records, policy=policy, transport=transport, existing_authorized_ids=existing_authorized_ids)
        applied = self.controller.apply(result.allowlist_plan, confirmed=confirmed)
        self.status.policy_mode = policy.mode.value
        self.status.last_reconcile_at = result.observed_at
        self.status.authorized_container_ids = sorted(result.allowlist_plan.authorized_ids)
        self.status.unauthorized_container_ids = sorted({probe.container_id for probe in result.probes if probe.container_id not in result.allowlist_plan.authorized_ids})
        self.status.last_apply = applied.as_dict()
        if applied.error:
            self.status.security_error = applied.error
        return OrchestrationResult(result, applied, self.status)
