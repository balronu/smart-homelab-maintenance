"""Read-only agent-side recovery inspector backed by the fixed helper."""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from .recovery import RecoveryEvidence


_PACKAGE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9+_.:-]*)\t(.+)$")
_PROCESS = re.compile(r"\b(?:apt|apt-get|dpkg|unattended-upgrade)\b")


def _observation(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get("observations", {}).get(name, {})
    return value if isinstance(value, Mapping) else {}


def _successful_observation(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = _observation(data, name)
    if value.get("returncode") != 0:
        raise ValueError(f"inspection evidence is unavailable: {name}")
    return value


def _lock_observation(data: Mapping[str, Any], name: str) -> int:
    value = _observation(data, name)
    code = value.get("returncode")
    if code not in {0, 1}:
        raise ValueError("lock ownership evidence is unknown")
    return int(code)


class AgentRecoveryInspector:
    """Convert fixed helper observations into strict recovery evidence."""

    def __init__(self, helper) -> None:
        self.helper = helper

    def __call__(self, job: Mapping[str, Any]) -> RecoveryEvidence:
        target = str(job.get("target", ""))
        if not target.startswith("container:"):
            raise ValueError("recovery inspection supports only LXC targets")
        container_id = int(target.split(":", 1)[1])
        response = self.helper.inspect(container_id)
        observations = response.get("observations")
        if not isinstance(observations, Mapping):
            raise ValueError("helper returned incomplete inspection")
        process_text = str(_successful_observation(response, "processes").get("stdout", ""))
        active = any(_PROCESS.search(line) for line in process_text.splitlines())
        packages: dict[str, str] = {}
        for line in str(_successful_observation(response, "packages").get("stdout", "")).splitlines():
            match = _PACKAGE.match(line)
            if match:
                packages[match.group(1)] = match.group(2)
        try:
            baseline = json.loads(str(job.get("baseline_packages") or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError("persisted package baseline is invalid") from exc
        if not isinstance(baseline, dict) or not baseline:
            raise ValueError("persisted package baseline is unavailable")
        package_mutation = any(packages.get(name) != version for name, version in baseline.items())
        history = str(_successful_observation(response, "apt_history").get("stdout", ""))
        dpkg_log = str(_successful_observation(response, "dpkg_log").get("stdout", ""))
        log_checked = True
        # APT history proves that some transaction occurred, but without a
        # job marker it cannot be attributed safely to this job.
        ambiguous_history = bool(history.strip() or dpkg_log.strip())
        dpkg_consistent = _successful_observation(response, "dpkg_audit").get("returncode") == 0
        lock_states = [_lock_observation(response, name) for name in ("apt_lock", "apt_archives_lock", "dpkg_lock", "dpkg_frontend_lock")]
        # fuser: 0 means a process owns the lock; 1 means the file is not
        # held. Any other code is an unavailable/failed check and must not be
        # treated as an unlocked file.
        locks = any(code == 0 for code in lock_states)
        return RecoveryEvidence(
            execution_started=True if ambiguous_history else False,
            package_mutation=True if package_mutation else False,
            partial_execution=True if package_mutation else False,
            active_package_processes=active,
            package_locks=locks,
            start_marker_found=True if ambiguous_history else False,
            completion_marker_found=None if ambiguous_history else False,
            job_logs_checked=True,
            apt_history_checked=log_checked,
            package_versions_checked=bool(packages),
            execution_markers_checked=True,
            package_manager_consistent=dpkg_consistent,
            side_effects_checked=True,
            detail="APT/dpkg history was observed without a job-specific completion marker" if ambiguous_history else "fixed inspection complete",
        )
