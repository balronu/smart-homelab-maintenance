from __future__ import annotations

import tempfile
import threading
import asyncio
import time
import json
import ssl
import urllib.error
import unittest
from unittest.mock import patch
from pathlib import Path

from agent.smart_homelab_maintenance.adapters import default_registry
from agent.smart_homelab_maintenance.api import ApiApplication
from agent.smart_homelab_maintenance.api_models import JobCreatePayload
from agent.smart_homelab_maintenance.discovery import DiscoveryService, FixtureProxmoxBackend, phase1_fixture
from agent.smart_homelab_maintenance.proxmox_backend import (
    FixtureProxmoxClient, ProxmoxApiClient, ProxmoxAuthenticationError,
    ProxmoxClientConfig, ProxmoxInventoryBackend,
)
from agent.smart_homelab_maintenance.server import AgentServerConfig, load_credential, load_runtime_config
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
from agent.smart_homelab_maintenance.http_transport import AgentHttpTransport, TransportConfig, TransportError, validate_agent_url
from custom_components.smart_homelab_maintenance.http_transport import validate_agent_url as validate_integration_agent_url
from custom_components.smart_homelab_maintenance.http_transport import (
    AgentHttpTransport as IntegrationAgentHttpTransport,
    TransportConfig as IntegrationTransportConfig,
    validate_ca_file,
    TransportError as IntegrationTransportError,
)
from custom_components.smart_homelab_maintenance.config_flow import validate_config
from custom_components.smart_homelab_maintenance.update import update_value
from custom_components.smart_homelab_maintenance.coordinator import SmartHomelabCoordinator
from custom_components.smart_homelab_maintenance.compatibility import evaluate_agent
from custom_components.smart_homelab_maintenance.sensor import coordinator_sensors
from agent.smart_homelab_maintenance import __version__ as agent_version
from custom_components.smart_homelab_maintenance.const import VERSION as integration_version


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tempdir.name) / "jobs.sqlite")
        self.repo = JobRepository(self.db, max_log_entries=3)

    def tearDown(self) -> None:
        self.repo.close()
        self.tempdir.cleanup()

    def test_release_versions_are_consistent_across_runtime_and_manifest(self) -> None:
        manifest = json.loads((Path(__file__).parents[1] / "custom_components" / "smart_homelab_maintenance" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(agent_version, integration_version)
        self.assertEqual(manifest["version"], integration_version)

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
        clean = validate_config({"agent_url": "https://agent.home.arpa:1", "token": "fixture", "scan_interval": 30})
        self.assertEqual(clean["scan_interval"], 30)
        with self.assertRaises(ValueError):
            validate_config({"agent_url": "http://remote.invalid", "token": "fixture"})
        value = update_value({"app_id": "paperless", "installed_version": "1", "available_version": "2", "update_supported": False, "blocked_reasons": ["manual_recovery_required"]})
        self.assertFalse(value.has_update)
        self.assertFalse(value.update_execution_enabled)

    def test_http_transport_uses_timeout_size_and_api_version_guards(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                self.limit = limit
                return json.dumps({"schema_version": "1", "data": {"status": "ok"}}).encode()

        with patch("agent.smart_homelab_maintenance.http_transport.urllib.request.urlopen", return_value=Response()) as open_url:
            client = AgentHttpTransport(TransportConfig("https://agent.home.arpa:443", "fixture", timeout_seconds=2))
            response = asyncio.run(client.health())
            self.assertEqual(response["data"]["status"], "ok")
            args, kwargs = open_url.call_args
            request = args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer fixture")
            self.assertTrue(kwargs["context"].check_hostname)
            self.assertEqual(kwargs["context"].verify_mode, ssl.CERT_REQUIRED)

        with patch(
            "agent.smart_homelab_maintenance.http_transport.urllib.request.urlopen",
            side_effect=urllib.error.URLError(ssl.SSLCertVerificationError("fixture certificate")),
        ):
            with self.assertRaises(TransportError) as raised:
                asyncio.run(AgentHttpTransport(TransportConfig("https://agent.home.arpa", "fixture")).health())
            self.assertEqual(raised.exception.code, "tls_error")

        with self.assertRaises(ValueError):
            TransportConfig("http://127.0.0.1", "fixture")
        with self.assertRaises(ValueError):
            validate_agent_url("https://public.example")

    def test_integration_dry_run_transport_handles_success_error_timeout_and_tls(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                self.limit = limit
                return json.dumps({"schema_version": "1", "data": {"status": "simulated"}}).encode()

        config = IntegrationTransportConfig("https://agent.home.arpa:443", "fixture", timeout_seconds=1)
        client = IntegrationAgentHttpTransport(config)
        with patch(
            "custom_components.smart_homelab_maintenance.http_transport.urllib.request.urlopen",
            return_value=Response(),
        ):
            result = asyncio.run(client.dry_run("host"))
        self.assertEqual(result["data"]["status"], "simulated")

        with patch(
            "custom_components.smart_homelab_maintenance.http_transport.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("https://agent.home.arpa", 503, "fixture", {}, None),
        ):
            with self.assertRaises(IntegrationTransportError) as raised:
                asyncio.run(client.dry_run("host"))
        self.assertEqual(raised.exception.code, "http_error")

        with patch.object(IntegrationAgentHttpTransport, "_post_json_sync", side_effect=lambda *args: time.sleep(0.2)):
            short = IntegrationTransportConfig("https://agent.home.arpa:443", "fixture", timeout_seconds=0.1)
            with self.assertRaises(IntegrationTransportError) as raised:
                asyncio.run(IntegrationAgentHttpTransport(short).dry_run("host"))
        self.assertEqual(raised.exception.code, "timeout")

        with patch(
            "custom_components.smart_homelab_maintenance.http_transport.urllib.request.urlopen",
            side_effect=urllib.error.URLError(ssl.SSLCertVerificationError("fixture certificate")),
        ):
            with self.assertRaises(IntegrationTransportError) as raised:
                asyncio.run(client.dry_run("host"))
        self.assertEqual(raised.exception.code, "tls_error")

        with self.assertRaises(IntegrationTransportError) as raised:
            asyncio.run(client.dry_run("container:0"))
        self.assertEqual(raised.exception.code, "invalid_target")

    def test_private_ca_path_is_bounded_to_ha_ssl_directory(self) -> None:
        self.assertEqual(validate_ca_file("/ssl/agent-ca.pem"), "/ssl/agent-ca.pem")
        self.assertEqual(validate_ca_file(""), None)
        for value in ("agent-ca.pem", "/config/secrets.yaml", "/ssl/../config/ca.pem", "/ssl/ca.txt"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_ca_file(value)

    def test_ip_based_agent_url_is_private_and_tls_only(self) -> None:
        agent_ip = ".".join(("192", "168", "178", "199"))
        self.assertEqual(
            validate_integration_agent_url(f"https://{agent_ip}:48128"),
            f"https://{agent_ip}:48128",
        )
        with self.assertRaises(ValueError):
            validate_integration_agent_url(f"http://{agent_ip}:48128")
        with self.assertRaises(ValueError):
            validate_integration_agent_url("https://8.8.8.8:48128")

    def test_mock_agent_to_coordinator_to_entity_data_flow(self) -> None:
        class FakeTransport:
            async def host(self):
                return {"data": {"name": "fixture-host", "online": True}}
            async def virtual_machines(self):
                return {"data": {"items": [{"vmid": 104, "name": "fixture-vm", "status": "running"}]}}
            async def containers(self):
                return {"data": {"items": [{"container_id": 101, "name": "fixture", "running": True}]}}
            async def jobs(self):
                return {"data": {"items": [{"job_id": "j1", "state": "running"}]}}
            async def capabilities(self):
                return {"data": {"execution_enabled": False}}
            async def health(self):
                return {"data": {"agent_version": "0.1.0-beta.37", "api_contract": "1.1"}}
            async def updates(self):
                return {"data": {"items": []}}

        async def scenario() -> None:
            coordinator = SmartHomelabCoordinator(None, {"agent_url": "https://agent.home.arpa:1", "token": "fixture"})
            coordinator.transport = FakeTransport()
            data = await coordinator.async_update()
            self.assertTrue(data.connected)
            self.assertEqual(data.containers[0]["container_id"], 101)
            self.assertEqual(data.host["name"], "fixture-host")
            self.assertEqual(data.virtual_machines[0]["vmid"], 104)
            self.assertEqual(coordinator_sensors(data)[1].value, 1)
            self.assertFalse(data.capabilities["execution_enabled"])
            self.assertEqual(data.compatibility.status, "current")

        asyncio.run(scenario())

    def test_update_http_error_does_not_hide_inventory(self) -> None:
        """The optional Beta.15 update endpoint must not blank core data."""
        class FakeTransport:
            async def host(self):
                return {"data": {"name": "fixture-host", "online": True}}
            async def virtual_machines(self):
                return {"data": {"items": [{"vmid": 104, "name": "fixture-vm", "status": "running"}]}}
            async def containers(self):
                return {"data": {"items": [{"container_id": 112, "name": "fixture-lxc", "running": True}]}}
            async def jobs(self):
                return {"data": {"items": []}}
            async def capabilities(self):
                return {"data": {"execution_enabled": False}}
            async def health(self):
                return {"data": {"agent_version": "0.1.0-beta.37", "api_contract": "1.1"}}
            async def updates(self):
                raise IntegrationTransportError("http_error", "fixture update endpoint returned HTTP 500")

        async def scenario() -> None:
            coordinator = SmartHomelabCoordinator(None, {"agent_url": "https://agent.home.arpa:1", "token": "fixture"})
            coordinator.transport = FakeTransport()
            data = await coordinator.async_update()
            self.assertTrue(data.connected)
            self.assertEqual(data.update_error, "http_error")
            self.assertEqual(data.host["name"], "fixture-host")
            self.assertEqual(data.virtual_machines[0]["vmid"], 104)
            self.assertEqual(data.containers[0]["container_id"], 112)
            self.assertEqual(data.updates, ())
            self.assertIsNone(data.error)

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

    def test_agent_compatibility_is_conservative(self) -> None:
        self.assertEqual(evaluate_agent("0.1.0-beta.37", "1.1").status, "current")
        self.assertEqual(evaluate_agent("0.1.0-beta.38", "1.1").status, "current")
        self.assertEqual(evaluate_agent("0.1.0-beta.36", "1.1").status, "current")
        self.assertEqual(evaluate_agent("0.1.0-beta.17", "1.1").status, "current")
        self.assertEqual(evaluate_agent("0.1.0-beta.23", "1.0").status, "incompatible")
        self.assertEqual(evaluate_agent("0.2.0-beta.1", "1.1").status, "incompatible")
        self.assertEqual(evaluate_agent(None, "1.1").status, "unknown")

    def test_discovery_capabilities_are_explicit_and_execution_off(self) -> None:
        for spec in default_registry().all():
            self.assertIn("execution_enabled", spec.capability_dict())
            self.assertFalse(spec.execution_enabled)

    def test_read_api_health_is_public_but_other_routes_are_authenticated(self) -> None:
        api = ApiApplication(DiscoveryService(FixtureProxmoxBackend(phase1_fixture())), self.repo, read_token="test-token")
        status, body = api.handle("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["agent_version"], "0.1.0-beta.42")
        self.assertEqual(body["data"]["api_contract"], "1.1")
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

    def test_proxmox_backend_is_read_only_dynamic_and_includes_vms(self) -> None:
        backend = ProxmoxInventoryBackend(FixtureProxmoxClient(
            {"name": "fixture-node", "release": "9.x", "online": True, "memory_used_bytes": 40, "memory_total_bytes": 100},
            lxcs=({"vmid": 101, "name": "fixture-lxc", "status": "stopped", "memory_used_bytes": 20, "memory_total_bytes": 50, "disk_used_bytes": 30, "disk_total_bytes": 100, "applications": []},),
            vms=({"vmid": 104, "name": "fixture-vm", "status": "running"},),
        ))
        self.assertEqual(backend.host()["name"], "fixture-node")
        self.assertEqual(backend.host()["memory_total_bytes"], 100)
        self.assertFalse(backend.containers()[0]["running"])
        self.assertEqual(backend.containers()[0]["memory_used_bytes"], 20)
        self.assertEqual(backend.containers()[0]["disk_total_bytes"], 100)
        self.assertEqual(backend.virtual_machines()[0]["vmid"], 104)

    def test_api_exposes_host_and_virtual_machines_without_update_routes(self) -> None:
        api = ApiApplication(DiscoveryService(FixtureProxmoxBackend(phase1_fixture())), self.repo, read_token="token")
        status, body = api.handle("GET", "/api/v1/host", headers={"Authorization": "Bearer token"})
        self.assertEqual(status, 200)
        self.assertTrue(body["data"]["online"])
        status, body = api.handle("GET", "/api/v1/virtual-machines", headers={"Authorization": "Bearer token"})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["items"], [])
        self.assertEqual(api.handle("POST", "/api/v1/update", headers={"Authorization": "Bearer token"})[0], 400)

    def test_agent_server_requires_tls_and_systemd_credential_is_not_logged(self) -> None:
        with self.assertRaises(ValueError):
            AgentServerConfig(certificate=None, private_key=None)
        credential = Path(self.tempdir.name) / "api-token"
        credential.write_text("fixture-token\n", encoding="utf-8")
        self.assertEqual(load_credential(credential), "fixture-token")
        credential.write_text("fixture token\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_credential(credential)

    def test_real_proxmox_client_is_bounded_read_only_and_normalizes_inventory(self) -> None:
        class Response:
            def __init__(self, payload):
                self.status = 200
                self.payload = json.dumps({"data": payload}).encode()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit):
                self.limit = limit
                return self.payload

        responses = {
            "status": {"pveversion": "pve-manager/8.4", "kversion": "6.8", "status": "online"},
            "lxc": [{"vmid": 101, "name": "fixture", "status": "running", "maxmem": 100, "mem": 40, "maxdisk": 1000, "disk": 250}],
            "qemu": [{"vmid": 104, "name": "ha", "status": "running", "cpu": 0.125, "mem": 600, "maxmem": 1000, "disk": 400, "maxdisk": 2000, "uptime": 3600}],
        }
        calls = []
        def opener(request, **kwargs):
            calls.append((request, kwargs))
            return Response(responses[request.full_url.rsplit("/", 1)[-1] if request.full_url.endswith(("status", "lxc", "qemu")) else ""])

        config = ProxmoxClientConfig("https://pve.home.arpa/api2/json", "pve", "fixture-token")
        client = ProxmoxApiClient(config, opener=opener)
        host = client.node_status()
        self.assertEqual(host["release"], "pve-manager/8.4")
        self.assertTrue(host["online"])
        self.assertIsNone(host["cpu_percent"])
        self.assertEqual(client.lxc_list()[0]["memory_available_bytes"], 60)
        vm = client.vm_list()[0]
        self.assertEqual(vm["vmid"], 104)
        self.assertEqual(vm["cpu_percent"], 12.5)
        self.assertEqual(vm["memory_used_bytes"], 600)
        self.assertEqual(vm["memory_total_bytes"], 1000)
        self.assertNotIn("memory_available_bytes", vm)
        self.assertNotIn("free_bytes", vm)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(call[0].get_method() == "GET" for call in calls))
        self.assertTrue(all(call[0].get_header("Authorization") == "PVEAPIToken fixture-token" for call in calls))

    def test_proxmox_client_rejects_public_urls_and_auth_errors_are_structured(self) -> None:
        with self.assertRaises(ValueError):
            ProxmoxClientConfig("https://public.example/api2/json", "pve", "fixture-token")
        with self.assertRaises(ValueError):
            ProxmoxClientConfig("http://pve.home.arpa/api2/json", "pve", "fixture-token")

        class ErrorResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b"{}"
        def opener(request, **kwargs):
            raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", {}, None)
        client = ProxmoxApiClient(ProxmoxClientConfig("https://pve.home.arpa/api2/json", "pve", "fixture-token"), opener=opener)
        with self.assertRaises(ProxmoxAuthenticationError):
            client.node_status()

    def test_runtime_config_is_non_secret_and_enforces_disabled_execution(self) -> None:
        config_path = Path(self.tempdir.name) / "agent.toml"
        config_path.write_text(
            'listen_host = "agent.home.arpa"\nlisten_port = 48128\n'
            f'state_directory = "{self.tempdir.name}"\n'
            'certificate = "/tmp/agent.crt"\nprivate_key = "/tmp/agent.key"\n'
            'proxmox_url = "https://pve.home.arpa/api2/json"\nproxmox_node = "pve"\n'
            'execution_enabled = false\n', encoding="utf-8")
        config = load_runtime_config(config_path)
        self.assertFalse(config.server.execution_enabled)
        self.assertEqual(config.proxmox.node, "pve")

    def test_runtime_config_accepts_only_explicit_update_target_metadata(self) -> None:
        config_path = Path(self.tempdir.name) / "agent-updates.toml"
        config_path.write_text(
            'listen_host = "agent.home.arpa"\nlisten_port = 48128\n'
            f'state_directory = "{self.tempdir.name}"\n'
            'certificate = "/tmp/agent.crt"\nprivate_key = "/tmp/agent.key"\n'
            'proxmox_url = "https://pve.home.arpa/api2/json"\nproxmox_node = "pve"\n'
            '[update_targets."container:107"]\n'
            'authorized = true\nos_name = "Debian"\nos_version = "12"\npackage_manager = "apt"\n', encoding="utf-8")
        config = load_runtime_config(config_path)
        self.assertEqual(config.update_targets["container:107"]["package_manager"], "apt")


if __name__ == "__main__":
    unittest.main()
