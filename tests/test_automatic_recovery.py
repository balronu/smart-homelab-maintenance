from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent.smart_homelab_maintenance.jobs import JobRepository
from agent.smart_homelab_maintenance.recovery import RecoveryEvidence, classify_recovery
from agent.smart_homelab_maintenance.types import JobRequest, JobState


def evidence(**changes):
    value = RecoveryEvidence(
        execution_started=False, package_mutation=False, partial_execution=False,
        active_package_processes=False, package_locks=False,
        start_marker_found=False, completion_marker_found=False,
        job_logs_checked=True, apt_history_checked=True,
        package_versions_checked=True, execution_markers_checked=True,
        package_manager_consistent=True, side_effects_checked=True,
    )
    return RecoveryEvidence(**{**value.as_dict(), **changes})


class AutomaticRecoveryTests(unittest.TestCase):
    def test_classifier_never_uses_versions_alone(self):
        result = classify_recovery(evidence(side_effects_checked=False))
        self.assertEqual(result.outcome, "recovery_blocked")

    def test_classifier_distinguishes_running_completed_and_partial(self):
        self.assertEqual(classify_recovery(evidence(active_package_processes=True)).outcome, "running")
        self.assertEqual(classify_recovery(evidence(execution_started=True, start_marker_found=True,
                                                     completion_marker_found=True)).outcome, "reconciled_completed")
        self.assertEqual(classify_recovery(evidence(package_mutation=True)).outcome, "recovery_blocked")
        self.assertEqual(classify_recovery(evidence()).outcome, "reconciled_not_executed")

    def test_events_are_append_only_and_target_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = JobRepository(str(Path(directory) / "jobs.sqlite"))
            first = repo.create(JobRequest("container:107", "update", None, "key-107-123456", "digest-107"))
            second = repo.create(JobRequest("container:101", "update", None, "key-101-123456", "digest-101"))
            repo.transition(first, JobState.PREFLIGHT)
            repo.transition(first, JobState.MANUAL_RECOVERY, phase="recovery")
            repo.transition(second, JobState.PREFLIGHT)
            self.assertTrue(repo.has_unresolved_target("container:107"))
            self.assertTrue(repo.has_unresolved_target("container:101"))
            events = repo.audit_events(first)
            self.assertGreaterEqual(len(events), 3)
            self.assertEqual(events[0]["event"], "created")
            self.assertEqual(events[-1]["event"], "state_changed")
            repo.close()

    def test_automatic_reconcile_completed_is_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = JobRepository(str(Path(directory) / "jobs.sqlite"))
            job = repo.create(JobRequest("container:101", "update", None, "key-complete-1234", "digest-12345678"))
            repo.transition(job, JobState.PREFLIGHT)
            repo.transition(job, JobState.MANUAL_RECOVERY, phase="recovery")
            result = repo.reconcile_from_evidence(job, container_id=101,
                                                   evidence=evidence(execution_started=True,
                                                                     start_marker_found=True,
                                                                     completion_marker_found=True))
            self.assertTrue(result["accepted"])
            self.assertEqual(repo.get(job)["state"], JobState.RECONCILED_COMPLETED)
            repo.close()

    def test_bounded_runner_never_retries_and_records_context(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = JobRepository(str(Path(directory) / "jobs.sqlite"))
            job = repo.create(JobRequest("container:102", "update", None, "key-runner-1234", "digest-12345678"))
            repo.set_execution_context(job, plan_digest="sha256-plan", baseline_packages={"demo": "1.0"})
            repo.transition(job, JobState.PREFLIGHT)
            repo.transition(job, JobState.MANUAL_RECOVERY, phase="recovery")
            calls = []
            results = repo.run_recovery(lambda record: (calls.append(record["job_id"]) or evidence()), limit=1)
            self.assertEqual(calls, [job])
            self.assertEqual(results[0]["outcome"], "not_executed")
            self.assertEqual(repo.get(job)["plan_digest"], "sha256-plan")
            repo.close()


if __name__ == "__main__":
    unittest.main()
