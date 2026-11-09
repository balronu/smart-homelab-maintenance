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


def test_orchestration_api_accepts_dynamic_installation_status():
    calls = []

    def status():
        calls.append(True)
        return OrchestrationStatus()

    application = ApiApplication(_Discovery(), _Jobs(), read_token="fixture", orchestration_status=status)
    code, response = application.handle("GET", "/api/v1/orchestration", headers={"Authorization": "Bearer fixture"})
    assert code == 200 and response["data"]["status"] == "unavailable"
    assert calls == [True]


def test_orchestration_status_uses_helper_policy_reader_and_hides_failures(monkeypatch):
    healthy = status_module.read_installation_status(policy_reader=lambda: {"110": {"authorized": True}})
    assert healthy.security_error is None
    assert healthy.authorized_container_ids == [110]

    failed = status_module.read_installation_status(policy_reader=lambda: (_ for _ in ()).throw(PermissionError("secret path")))
    assert failed.security_error == "policy_unavailable"
    assert failed.integrity_ok is False


def test_orchestration_status_maps_legacy_and_split_grants_without_escalation():
    entries = {
        str(container_id): {"simulation_authorized": True, "update_authorized": False}
        for container_id in range(101, 109)
    }
    entries["110"] = {"authorized": True, "update_authorized": False}
    entries["111"] = {"simulation_authorized": False, "update_authorized": True}
    result = status_module.read_installation_status(
        policy_reader=lambda: entries,
        policy_mode_reader=lambda: "discover_only",
    )
    assert result.authorized_container_ids == [*range(101, 109), 110]
    assert 109 not in result.authorized_container_ids
    assert 111 not in result.authorized_container_ids
    assert result.policy_mode == "discover_only"


def test_orchestration_status_rejects_malformed_policy_and_unknown_mode():
    malformed = status_module.read_installation_status(
        policy_reader=lambda: {"110": {"simulation_authorized": "yes"}},
        policy_mode_reader=lambda: "discover_only",
    )
    assert malformed.integrity_ok is False
    assert malformed.authorized_container_ids == []
    assert malformed.security_error == "policy_unavailable"

    unknown = status_module.read_installation_status(
        policy_reader=lambda: {},
        policy_mode_reader=lambda: "unsafe_mode",
    )
    assert unknown.integrity_ok is False
    assert unknown.security_error == "policy_invalid"


def test_orchestration_status_preserves_only_real_reconcile_state():
    runtime = OrchestrationStatus(
        last_reconcile_at="2026-11-09T10:00:00+00:00",
        last_apply={"applied": False, "changed": False},
    )
    result = status_module.read_installation_status(
        policy_reader=lambda: {},
        policy_mode_reader=lambda: "auto_eligible",
        runtime_status=runtime,
    )
    assert result.last_reconcile_at == "2026-11-09T10:00:00+00:00"
    assert result.last_apply == {"applied": False, "changed": False}


def test_orchestration_api_returns_200_when_helper_status_is_healthy():
    status = OrchestrationStatus(helper_installed=True, discovery_socket_active=True, integrity_ok=True)
    application = ApiApplication(_Discovery(), _Jobs(), read_token="fixture", orchestration_status=status)
    code, response = application.handle("GET", "/api/v1/orchestration", headers={"Authorization": "Bearer fixture"})
    assert code == 200
    assert response["data"]["status"] == "ok"
