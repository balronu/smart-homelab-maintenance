from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from agent.smart_homelab_maintenance.api import ApiApplication
from agent.smart_homelab_maintenance.discovery import DiscoveryService, FixtureProxmoxBackend, phase1_fixture
from agent.smart_homelab_maintenance.jobs import JobRepository
from agent.smart_homelab_maintenance.updates import AptCommandRunner, ProbeTarget, UpdateService, _parse_apt, make_targets


def target(os_name="Debian"):
    return ProbeTarget("container:107", "fixture", 107, os_name, "12", "apt")


class Runner:
    def __init__(self, stdout="", stderr="", code=0):
        self.stdout, self.stderr, self.code = stdout, stderr, code
        self.calls = []

    def simulate(self, vmid=None):
        self.calls.append(vmid)
        return self.code, self.stdout, self.stderr


def service(runner, targets=(target(),), clock=None):
    return UpdateService(lambda: targets, runner=runner, clock=clock)


def test_apt_parser_distinguishes_current_updates_security_and_removal():
    packages, held, conflicts, removals = _parse_apt(
        "Inst openssl [3.0.1] (3.0.2-1~deb12u1 Debian:12.0/stable-security [amd64])\n"
        "Inst curl [7.0] (7.1)\nRemv obsolete [1.0]\n", ""
    )
    assert [item.name for item in packages] == ["openssl", "curl"]
    assert packages[0].security is True
    assert removals == ("obsolete",)
    assert held == () and conflicts == ()


def test_update_check_reports_current_and_unsupported_without_faking_values():
    current = service(Runner("0 upgraded, 0 newly installed, 0 to remove."))
    result = current.check("container:107")
    assert result.status == "current" and result.available_count == 0
    unsupported = service(Runner(), (target("Alpine"),)).check("container:107")
    assert unsupported.status == "unsupported" and unsupported.available_count is None


def test_update_check_distinguishes_unauthorized_target_and_explicit_guest_allowlist():
    denied = service(Runner(), (ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", False),)).check("container:107")
    assert denied.status == "unauthorized" and denied.supported is False
    targets = make_targets({"name": "pve"}, [{"container_id": 107, "name": "fixture", "os_name": "unknown"}], {
        "container:107": {"authorized": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt"},
    })
    assert targets[1].authorized is True and targets[1].os_name == "Debian" and targets[1].package_manager == "apt"
    vm = make_targets({"name": "pve"}, [], virtual_machines=[{"vmid": 104, "name": "haos"}])[1]
    assert service(Runner(), (vm,)).check("vm:104").status == "not_checked"


def test_update_api_preserves_explicit_statuses_instead_of_unknown_fallbacks():
    unsupported = service(Runner(), (target("Alpine"),)).check("container:107").as_dict()
    unauthorized = service(Runner(), (ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", False),)).check("container:107").as_dict()
    assert unsupported["status"] == "unsupported"
    assert unauthorized["status"] == "unauthorized"
    assert unsupported["available_count"] is None and unauthorized["available_count"] is None


def test_update_result_marks_old_successful_result_stale():
    result = service(Runner("0 upgraded, 0 newly installed, 0 to remove.")).check("container:107")
    old = result.__class__(result.target, result.name, result.reachable, result.supported, result.os_name, result.os_version, result.package_manager, result.status, result.available_count, result.security_count, result.packages, result.held_packages, result.conflicts, result.removals, "2000-01-01T00:00:00+00:00", result.error, result.stale_after_seconds, result.plan_digest, result.dry_run_supported)
    data = old.as_dict()
    assert data["status"] == "stale" and data["fresh"] is False


def test_update_check_reports_errors_and_permission_as_unknown():
    class PermissionRunner:
        def simulate(self, vmid=None):
            raise PermissionError("denied")
    result = service(PermissionRunner()).check("container:107")
    assert result.status == "unknown" and result.reachable is False
    failed = service(Runner("", "E: broken dependency", 100)).check("container:107")
    assert failed.status == "error" and failed.available_count is None


def test_dry_run_requires_confirmation_and_refuses_changed_plan():
    runner = Runner("Inst curl [7.0] (7.1)")
    now = [100.0]
    checked = service(runner, clock=lambda: now[0])
    with pytest.raises(Exception):
        checked.dry_run("container:107", confirmed=False)
    assert checked.check("container:107").status == "updates_available"
    result = checked.dry_run("container:107", confirmed=True)
    assert result["simulation"] is True and result["success"] is True and result["safe"] is True
    runner.stdout = "Inst curl [7.0] (7.2)"
    changed = checked.dry_run("container:107", confirmed=True)
    assert changed["success"] is False and "stale" in changed["error"]


def test_simulation_command_is_fixed_and_never_an_install_or_refresh():
    calls = []
    class Completed:
        returncode, stdout, stderr = 0, "", ""
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return Completed()
    runner = AptCommandRunner(run=run)
    assert runner.simulate()[0] == 0
    argv = calls[0][0]
    assert argv[-1] == "upgrade" and "--simulate" in argv and "--no-remove" in argv
    assert "install" not in argv and "update" not in argv


def test_api_exposes_dry_run_and_rejects_future_execution():
    runner = Runner("Inst curl [7.0] (7.1)")
    updates = service(runner)
    with tempfile.TemporaryDirectory() as directory:
        repo = JobRepository(str(Path(directory) / "jobs.sqlite"))
        api = ApiApplication(DiscoveryService(FixtureProxmoxBackend(phase1_fixture())), repo, updates=updates, read_token="token")
        headers = {"Authorization": "Bearer token"}
        status, body = api.handle("GET", "/api/v1/updates/container:107", headers=headers)
        assert status == 200 and body["data"]["status"] == "updates_available"
        status, body = api.handle("POST", "/api/v1/updates/container:107/dry-run", headers=headers, body=b'{"confirm":true}')
        assert status == 200 and body["data"]["simulation"] is True
        status, body = api.handle("POST", "/api/v1/updates/container:107/execute", headers=headers, body=b'{}')
        assert status == 400 and body["error"]["code"] == "invalid_request"
        repo.close()
