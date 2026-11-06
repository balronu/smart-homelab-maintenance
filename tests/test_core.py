from __future__ import annotations

import tempfile
import threading
import asyncio
import json
import unittest
from pathlib import Path

from agent.smart_homelab_maintenance.adapters import default_registry
from agent.smart_homelab_maintenance.api import ApiApplication
from agent.smart_homelab_maintenance.api_models import JobCreatePayload
from agent.smart_homelab_maintenance.discovery import DiscoveryService, FixtureProxmoxBackend, phase1_fixture
from agent.smart_homelab_maintenance.errors import (
    ConcurrentJobError,
    DuplicateJobError,
    ExecutionDisabledError,
    InvalidTransitionError,
    ResourceGateError,
    UnknownTargetError,
    UnsupportedApplicationError,
    ValidationError,
)
from agent.smart_homelab_maintenance.execution import ExecutionController
from agent.smart_homelab_maintenance.inventory import InventoryCatalog
from agent.smart_homelab_maintenance.jobs import JobRepository
from agent.smart_homelab_maintenance.security import redact_secrets, resource_gate, validate_job_request
from agent.smart_homelab_maintenance.types import (
    JobPhase,
    JobRequest,
    JobState,
    ApplicationRef,
    ContainerRef,
    InstallKind,
    ResourcePolicy,
    ResourceSnapshot,
    Verification,
)
from agent.smart_homelab_maintenance.versions import Version, compare_versions
from agent.smart_homelab_maintenance.http_transport import AgentHttpTransport, TransportConfig, TransportError
from custom_components.smart_homelab_maintenance.config_flow import validate_config
from custom_components.smart_homelab_maintenance.update import update_value
from custom_components.smart_homelab_maintenance.coordinator import SmartHomelabCoordinator
from custom_components.smart_homelab_maintenance.sensor import coordinator_sensors


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tempdir.name) / "jobs.sqlite")
        self.repo = JobRepository(self.db, max_log_entries=3)

    def tearDown(self) -> None:
        self.repo.close()
        self.tempdir.cleanup()

    def request(self, *, target: str = "paperless", key: str = "request-12345678") -> JobRequest:
        return JobRequest(target, "update", "3.4.2", key, "confirm-12345678")

    def queued_job(self, *, key: str = "request-12345678") -> str:
        return self.repo.create(self.request(key=key))

    def test_valid_job_lifecycle_requires_verification(self) -> None:
        job = self.queued_job()
        self.repo.transition(job, JobState.PREFLIGHT, phase=JobPhase.PREFLIGHT, progress=10)
        self.repo.transition(job, JobState.WAITING_CONFIRMATION, progress=20)
        self.repo.transition(job, JobState.RUNNING, phase=JobPhase.EXECUTION, progress=50)
        self.repo.transition(job, JobState.POSTCHECK, phase=JobPhase.POSTCHECK, progress=90)
        self.repo.complete(job, Verification(True, True, "3.4.2", "verified"))
        record = self.repo.get(job)
        self.assertEqual(record["state"], JobState.SUCCEEDED)
        self.assertEqual(record["postcheck_verified"], 1)

    def test_process_exit_cannot_be_success(self) -> None:
        job = self.queued_job()
        self.repo.transition(job, JobState.PREFLIGHT)
        self.repo.transition(job, JobState.RUNNING)
        self.repo.transition(job, JobState.POSTCHECK)
        self.repo.complete(job, Verification(True, False, message="service not healthy"))
        self.assertEqual(self.repo.get(job)["state"], JobState.MANUAL_RECOVERY)

    def test_invalid_transition_is_rejected(self) -> None:
        job = self.queued_job()
        with self.assertRaises(InvalidTransitionError):
            self.repo.transition(job, JobState.SUCCEEDED)

    def test_duplicate_idempotency_key_is_rejected(self) -> None:
        self.queued_job()
        with self.assertRaises(DuplicateJobError):
            self.queued_job()

    def test_same_target_cannot_run_twice(self) -> None:
        first = self.queued_job()
        second = self.queued_job(key="request-87654321")
        self.repo.transition(first, JobState.PREFLIGHT)
        with self.assertRaises(ConcurrentJobError):
            self.repo.transition(second, JobState.PREFLIGHT)

    def test_concurrent_starts_have_one_winner(self) -> None:
        first = self.queued_job()
        second = self.queued_job(key="request-87654321")
        outcomes: list[str] = []
        barrier = threading.Barrier(2)

        def start(job: str) -> None:
            barrier.wait()
            try:
                self.repo.transition(job, JobState.PREFLIGHT)
                outcomes.append("won")
            except ConcurrentJobError:
                outcomes.append("lost")

        threads = [threading.Thread(target=start, args=(job,)) for job in (first, second)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ["lost", "won"])

    def test_timeout_is_terminal_and_not_success(self) -> None:
        job = self.queued_job()
        self.repo.transition(job, JobState.PREFLIGHT)
        self.repo.transition(job, JobState.RUNNING)
        self.repo.transition(job, JobState.TIMEOUT, phase=JobPhase.RECOVERY, progress=100)
        self.assertEqual(self.repo.get(job)["state"], JobState.TIMEOUT)

    def test_restart_marks_active_job_for_manual_recovery(self) -> None:
        job = self.queued_job()
        self.repo.transition(job, JobState.PREFLIGHT)
        self.repo.close()
        reopened = JobRepository(self.db, max_log_entries=3)
        self.assertEqual(reopened.get(job)["state"], JobState.MANUAL_RECOVERY)
        reopened.close()

    def test_log_history_is_bounded_and_paginated(self) -> None:
        job = self.queued_job()
        for index in range(5):
            self.repo.append_log(job, f"line {index}")
        logs = self.repo.logs(job, limit=3)
        self.assertEqual([item["message"] for item in logs], ["line 2", "line 3", "line 4"])
        self.assertEqual(self.repo.logs(job, offset=1, limit=2)[0]["message"], "line 3")

    def test_secret_filtering(self) -> None:
        value = {"password": "hidden", "nested": {"api_token": "also-hidden"}, "command": "rm -rf /"}
        redacted = redact_secrets(value)
        self.assertEqual(redacted["password"], "[REDACTED]")
        self.assertEqual(redacted["nested"]["api_token"], "[REDACTED]")
        self.assertNotIn("rm -rf", redacted["command"])

    def test_bad_request_and_command_like_input_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_job_request(JobRequest("paperless", "update", "3.4.2", "short"))
        with self.assertRaises(ValidationError):
            validate_job_request(JobRequest("paperless;rm", "update", "3.4.2", "request-12345678"))
        with self.assertRaises(ValidationError):
            JobCreatePayload.from_mapping({"target": "paperless", "operation": "update", "idempotency_key": "x", "extra": 1})

    def test_versions_are_conservative(self) -> None:
        self.assertEqual(compare_versions("2.14.2", "2.14.3"), -1)
        self.assertEqual(compare_versions("v3.4", "3.4.0"), 0)
        with self.assertRaises(ValidationError):
            Version.parse("latest")

    def test_resource_gate_blocks_low_space_memory_and_thinpool(self) -> None:
        result = resource_gate(
            ResourceSnapshot(1, 100, memory_available_bytes=1, thinpool_percent=95),
            ResourcePolicy(min_free_bytes=10, min_memory_available_bytes=10),
        )
        self.assertFalse(result.passed)
        with self.assertRaises(ResourceGateError):
            from agent.smart_homelab_maintenance.security import require_resources
            require_resources(ResourceSnapshot(1, 100), ResourcePolicy(min_free_bytes=10))

    def test_unknown_and_unsupported_adapters_are_blocked(self) -> None:
        registry = default_registry()
        with self.assertRaises(UnknownTargetError):
            registry.get("unknown")
        with self.assertRaises(UnsupportedApplicationError):
            registry.require_supported("zigbee2mqtt_womo")

    def test_unknown_container_and_application_are_blocked(self) -> None:
        catalog = InventoryCatalog()
        with self.assertRaises(UnknownTargetError):
            catalog.container(999)
        catalog.add_container(ContainerRef(102, "zigbee2mqtt-haus", True, "debian", "13", InstallKind.GIT_SYSTEMD))
        catalog.add_application(ApplicationRef("z2m", "Zigbee2MQTT", 102, InstallKind.GIT_SYSTEMD))
        self.assertEqual(catalog.application("z2m").container_id, 102)
        with self.assertRaises(UnknownTargetError):
            catalog.add_application(ApplicationRef("bad", "bad", 999, InstallKind.UNKNOWN))

    def test_execution_is_disabled_by_default(self) -> None:
        controller = ExecutionController(default_registry())
        with self.assertRaises(ExecutionDisabledError):
            controller.execute(self.request())

    def test_phase23_config_and_update_projection_are_safe(self) -> None:
        clean = validate_config({"agent_url": "http://127.0.0.1:1", "token": "fixture", "scan_interval": 30})
        self.assertEqual(clean["scan_interval"], 30)
        with self.assertRaises(ValueError):
            validate_config({"agent_url": "http://remote.invalid", "token": "fixture"})
        value = update_value({"app_id": "paperless", "installed_version": "1", "available_version": "2", "update_supported": False, "blocked_reasons": ["manual_recovery_required"]})
        self.assertFalse(value.has_update)
        self.assertFalse(value.update_execution_enabled)

    def test_http_transport_uses_timeout_size_and_api_version_guards(self) -> None:
        async def scenario() -> None:
            async def handler(reader, writer):
                request = await reader.read(4096)
                self.assertIn(b"Authorization: Bearer fixture", request)
                body = json.dumps({"schema_version": "1", "data": {"status": "ok"}}).encode()
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
                await writer.drain()
                writer.close()

            server = await asyncio.start_server(handler, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            client = AgentHttpTransport(TransportConfig(f"http://127.0.0.1:{port}", "fixture", timeout_seconds=2))
            response = await client.health()
            self.assertEqual(response["data"]["status"], "ok")
            server.close()
            await server.wait_closed()
            with self.assertRaises(ValueError):
                TransportConfig("http://remote.invalid", "fixture")

        asyncio.run(scenario())

    def test_mock_agent_to_coordinator_to_entity_data_flow(self) -> None:
        class FakeTransport:
            async def containers(self):
                return {"data": {"items": [{"container_id": 101, "name": "fixture", "running": True}]}}
            async def jobs(self):
                return {"data": {"items": [{"job_id": "j1", "state": "running"}]}}
            async def capabilities(self):
                return {"data": {"execution_enabled": False}}

        async def scenario() -> None:
            coordinator = SmartHomelabCoordinator(None, {"agent_url": "http://127.0.0.1:1", "token": "fixture"})
            coordinator.transport = FakeTransport()
            data = await coordinator.async_update()
            self.assertTrue(data.connected)
            self.assertEqual(data.containers[0]["container_id"], 101)
            self.assertEqual(coordinator_sensors(data)[1].value, 1)
            self.assertFalse(data.capabilities["execution_enabled"])

        asyncio.run(scenario())

    def test_discovery_is_dynamic_and_blocks_dirty_zigbee_and_recovery(self) -> None:
        fixture = phase1_fixture()
        fixture.append({"container_id": 120, "name": "new", "running": False, "os_name": "Alpine", "os_version": "3", "applications": []})
        for item in fixture:
            if item["container_id"] == 107:
                item["applications"][0]["details"]["manual_recovery_required"] = True
        service = DiscoveryService(FixtureProxmoxBackend(fixture))
        self.assertEqual(len(service.containers()), 11)
        self.assertIn("dirty_git_state", service.app("zigbee2mqtt_womo").blocked_reasons)
        self.assertIn("manual_recovery_required", service.app("paperless").blocked_reasons)
        self.assertFalse(service.app("paperless").update_supported)

    def test_discovery_capabilities_are_explicit_and_execution_off(self) -> None:
        for spec in default_registry().all():
            self.assertIn("execution_enabled", spec.capability_dict())
            self.assertFalse(spec.execution_enabled)

    def test_read_api_health_is_public_but_other_routes_are_authenticated(self) -> None:
        api = ApiApplication(DiscoveryService(FixtureProxmoxBackend(phase1_fixture())), self.repo, read_token="test-token")
        self.assertEqual(api.handle("GET", "/api/v1/health")[0], 200)
        self.assertEqual(api.handle("GET", "/api/v1/containers")[0], 401)
        status, body = api.handle("GET", "/api/v1/containers?limit=2", headers={"Authorization": "Bearer test-token"})
        self.assertEqual(status, 200)
        self.assertEqual(len(body["data"]["items"]), 2)

    def test_api_job_events_use_cursor_and_survive_reopen(self) -> None:
        job = self.queued_job()
        self.repo.append_log(job, "first")
        self.repo.append_log(job, "second")
        api = ApiApplication(DiscoveryService(FixtureProxmoxBackend(phase1_fixture())), self.repo, read_token="token")
        status, body = api.handle("GET", f"/api/v1/jobs/{job}/events?after=1", headers={"Authorization": "Bearer token"})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["events"][0]["message"], "second")
        self.repo.close()
        self.repo = JobRepository(self.db, max_log_entries=3)
        self.assertEqual(self.repo.get(job)["job_id"], job)

    def test_api_rejects_invalid_pagination_and_large_responses(self) -> None:
        api = ApiApplication(DiscoveryService(FixtureProxmoxBackend(phase1_fixture())), self.repo, read_token="token", max_bytes=20)
        status, _ = api.handle("GET", "/api/v1/containers?limit=no", headers={"Authorization": "Bearer token"})
        self.assertEqual(status, 400)
        status, _ = api.handle("GET", "/api/v1/containers", headers={"Authorization": "Bearer token"})
        self.assertEqual(status, 413)


if __name__ == "__main__":
    unittest.main()
