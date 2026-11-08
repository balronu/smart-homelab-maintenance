from pathlib import Path

from agent.smart_homelab_maintenance import orchestration_status as status_module
from agent.smart_homelab_maintenance.api import ApiApplication
from agent.smart_homelab_maintenance.orchestration_status import OrchestrationStatus


class _Discovery:
    def host(self): return {}
    def containers(self): return []
    def virtual_machines(self): return []


class _Jobs:
    pass


def test_installation_status_is_fail_closed_without_helper(monkeypatch, tmp_path: Path):
    paths = {
        "HELPER_PATH": tmp_path / "helper",
        "DISCOVERY_PATH": tmp_path / "discovery",
        "HELPER_UNIT_PATH": tmp_path / "helper.service",
        "DISCOVERY_UNIT_PATH": tmp_path / "discovery.service",
        "DISCOVERY_SOCKET_PATH": tmp_path / "discovery.sock",
        "ALLOWLIST_PATH": tmp_path / "allowlist.toml",
    }
    for name, path in paths.items():
        monkeypatch.setattr(status_module, name, path)
    result = status_module.read_installation_status()
    assert result.helper_installed is False
    assert result.discovery_socket_active is False
    assert result.integrity_ok is False
    assert result.policy_mode == "discover_only"


def test_orchestration_api_exposes_safe_status_without_ready_helper():
    application = ApiApplication(_Discovery(), _Jobs(), read_token="fixture", orchestration_status=OrchestrationStatus())
    code, response = application.handle("GET", "/api/v1/orchestration", headers={"Authorization": "Bearer fixture"})
    assert code == 200
    assert response["data"]["status"] == "unavailable"
    assert response["data"]["policy_mode"] == "discover_only"
    assert response["data"]["helper_installed"] is False
    assert response["data"]["integrity_ok"] is False
