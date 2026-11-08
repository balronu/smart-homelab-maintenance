"""Deterministic, non-writing policy reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .authorization import AuthorizationMode, AllowlistPlan, plan_allowlist
from .discovery_probe import ProbeResult, ProbeState, DiscoveryProbeTransport, evaluate_probe
from .policy import Policy, PolicyMode


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    policy: Policy
    probes: tuple[ProbeResult, ...]
    allowlist_plan: AllowlistPlan
    observed_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy.as_dict(),
            "observed_at": self.observed_at,
            "probes": [probe.as_dict() for probe in self.probes],
            "allowlist_plan": self.allowlist_plan.as_dict(),
        }


def reconcile(
    records: Sequence[Mapping[str, Any]],
    *,
    policy: Policy,
    transport: DiscoveryProbeTransport | None,
    existing_authorized_ids: set[int] | frozenset[int] = frozenset(),
) -> ReconcileResult:
    """Run one bounded sequential pass; no retries and no writes."""

    probe_results: list[ProbeResult] = []
    enriched: list[dict[str, Any]] = []
    for record in records:
        item = dict(record)
        if policy.mode is PolicyMode.AUTO_ELIGIBLE:
            probe = evaluate_probe(item, transport=transport, discovery_enabled=True)
        else:
            probe = evaluate_probe(item, transport=None, discovery_enabled=False)
        probe_results.append(probe)
        if policy.mode is PolicyMode.DISCOVER_ONLY:
            # No guest probe is allowed in the safe default; preserve the
            # caller's passive inventory evidence for existing manual policy.
            enriched.append(item)
            continue
        if probe.state is ProbeState.PASS:
            item.update({"os_name": probe.os_id, "os_version": probe.version_id, "package_manager": "apt"})
        else:
            item.update({"os_name": "unknown", "os_version": "unknown", "package_manager": None})
        enriched.append(item)
    mode = AuthorizationMode.AUTO_AUTHORIZE_SUPPORTED_RUNNING if policy.mode is PolicyMode.AUTO_ELIGIBLE else AuthorizationMode.DISCOVER_ONLY
    plan = plan_allowlist(
        enriched,
        mode=mode,
        existing_authorized_ids=existing_authorized_ids,
        manual_authorized_ids=policy.manual_authorized_ids,
    )
    return ReconcileResult(policy, tuple(probe_results), plan, datetime.now(timezone.utc).isoformat())
