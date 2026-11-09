import json
from pathlib import Path

from agent.smart_homelab_maintenance.api import ApiApplication
from agent.smart_homelab_maintenance.apply_controller import AllowlistApplyController
from agent.smart_homelab_maintenance.discovery import DiscoveryService, FixtureProxmoxBackend
from agent.smart_homelab_maintenance.discovery_probe import ProbeState
from agent.smart_homelab_maintenance.orchestration_service import OrchestrationService
from agent.smart_homelab_maintenance.orchestrator import LxcOrchestrator
from agent.smart_homelab_maintenance.policy import Policy, PolicyMode, PolicyStore


def _probe(version="12"):
    return {"os_release": f"ID=debian\nVERSION_ID={version}\n", "apt_version": "apt 3", "dpkg_version": "dpkg 1"}


class Probe:
    def __init__(self):
        self.calls = []

    def probe(self, container_id):
        self.calls.append(container_id)
        return _probe()


def _service(tmp_path: Path, mode=PolicyMode.DISCOVER_ONLY):
    discovery = DiscoveryService(FixtureProxmoxBackend([
        {"container_id": 110, "name": "legacy", "running": True},
        {"container_id": 112, "name": "stopped", "running": False},
    ]))
    probe = Probe()
    status = None
    store = PolicyStore(tmp_path / "policy.json", initial=Policy(mode))
    orchestrator = LxcOrchestrator(AllowlistApplyController(tmp_path / "allowlist.toml", require_root=False), status)
    return OrchestrationService(discovery, store, orchestrator, probe), probe


def test_policy_requires_generation_and_confirmation(tmp_path):
    service, _ = _service(tmp_path)
    prepared = service.prepare_policy({"mode": "auto_eligible", "generation": 0})
    assert prepared["requires_confirmation"] is True
    assert service.policy()["mode"] == "discover_only"
    updated = service.apply_policy({"mode": "auto_eligible", "generation": 0, "confirm": True})
    assert updated["policy"]["mode"] == "auto_eligible"
    assert updated["policy"]["generation"] == 1


def test_preview_is_explicit_and_excludes_stopped_container(tmp_path):
    service, probe = _service(tmp_path, PolicyMode.AUTO_ELIGIBLE)
    result = service.preview()
    assert result["requires_confirmation"] is True
    assert result["reconcile"]["allowlist_plan"]["authorized_ids"] == [110]
    assert 112 not in probe.calls
    assert result["reconcile"]["probes"][1]["state"] == ProbeState.STOPPED.value
    assert not (tmp_path / "allowlist.toml").exists()


def test_api_exposes_policy_preview_and_requires_apply_confirmation(tmp_path):
    service, _ = _service(tmp_path, PolicyMode.AUTO_ELIGIBLE)
    discovery = service.discovery
    app = ApiApplication(discovery, object(), read_token="token", orchestration=service)
    headers = {"Authorization": "Bearer token"}
    code, response = app.handle("GET", "/api/v1/policy", headers=headers)
    assert code == 200 and response["data"]["mode"] == "auto_eligible"
    code, response = app.handle("POST", "/api/v1/orchestration/preview", headers=headers, body=b"{}")
    assert code == 200
    token = response["data"]["preview_token"]
    code, response = app.handle("POST", "/api/v1/orchestration/apply", headers=headers,
                                body=json.dumps({"preview_token": token}).encode())
    assert code == 400
    assert not (tmp_path / "allowlist.toml").exists()
