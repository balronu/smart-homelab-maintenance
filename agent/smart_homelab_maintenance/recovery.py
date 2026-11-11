"""Fail-closed classification of interrupted package jobs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RecoveryEvidence:
    execution_started: bool | None
    package_mutation: bool | None
    partial_execution: bool | None
    active_package_processes: bool
    package_locks: bool
    start_marker_found: bool | None
    completion_marker_found: bool | None
    job_logs_checked: bool
    apt_history_checked: bool
    package_versions_checked: bool
    execution_markers_checked: bool
    package_manager_consistent: bool | None = None
    side_effects_checked: bool = False
    process_reference: str | None = None
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    outcome: str
    reason: str
    continue_monitoring: bool = False


def classify_recovery(evidence: RecoveryEvidence) -> RecoveryDecision:
    """Classify evidence; never infer non-execution from versions alone."""
    if evidence.active_package_processes:
        return RecoveryDecision("running", "a package process is still active", True)
    if not all((evidence.job_logs_checked, evidence.apt_history_checked,
                evidence.package_versions_checked, evidence.execution_markers_checked)):
        return RecoveryDecision("recovery_blocked", "independent evidence is incomplete")
    if evidence.partial_execution is True or evidence.package_mutation is True:
        if evidence.completion_marker_found is True and evidence.package_manager_consistent is True:
            return RecoveryDecision("reconciled_completed", "completion and package-manager consistency verified")
        return RecoveryDecision("recovery_blocked", "package execution or mutation lacks verified completion")
    if evidence.execution_started is True or evidence.start_marker_found is True:
        if evidence.completion_marker_found is True and evidence.package_manager_consistent is True:
            return RecoveryDecision("reconciled_completed", "started job has verified completion")
        return RecoveryDecision("recovery_blocked", "execution was documented but final state is unclear")
    if any(v is not False for v in (evidence.execution_started, evidence.package_mutation,
                                    evidence.partial_execution, evidence.start_marker_found,
                                    evidence.completion_marker_found)):
        return RecoveryDecision("recovery_blocked", "execution markers are ambiguous")
    if evidence.package_locks or not evidence.side_effects_checked or evidence.package_manager_consistent is not True:
        return RecoveryDecision("recovery_blocked", "locks, side effects, or package-manager consistency are not excluded")
    return RecoveryDecision("reconciled_not_executed", "required evidence excludes package execution")
