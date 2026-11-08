from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.smart_homelab_maintenance.api import ApiApplication
from agent.smart_homelab_maintenance.discovery import DiscoveryService, FixtureProxmoxBackend, phase1_fixture
from agent.smart_homelab_maintenance.jobs import JobRepository
from agent.smart_homelab_maintenance.updates import AptCommandRunner, AptUpdateReader, ProbeTarget, UpdateService, _parse_apt, _parse_apt_upgradable, make_targets


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


def test_passive_apt_reader_parses_existing_cache_without_simulation_flags():
    calls = []
    class Completed:
        returncode, stdout, stderr = 0, "Listing...\nopenssl/stable-security 3.0.2 [upgradable from: 3.0.1]\ncurl/stable 8.0 [upgradable from: 7.0]\n", ""
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return Completed()
    with patch("shutil.which", return_value="/usr/bin/apt"):
        reader = AptUpdateReader(run=run)
        code, stdout, stderr = reader.list_upgradable()
    packages = _parse_apt_upgradable(stdout, stderr)
    assert code == 0 and [item.name for item in packages] == ["openssl", "curl"]
    assert calls[0][0] == ["apt", "list", "--upgradable"]
    assert "simulate" not in calls[0][0] and "update" not in calls[0][0]


def test_passive_apt_parser_keeps_installed_versions_after_architecture_column():
    packages = _parse_apt_upgradable(
        "Listing...\n"
        "zlib1g/stable-security 1:1.3.1-1+deb13u1 amd64 "
        "[upgradable from: 1:1.3.1-1+b1]\n"
        "libpve-guest-common-perl/stable 6.0.7 all "
        "[upgradable from: 6.0.6]\n",
        "",
    )
    assert [(item.name, item.installed_version, item.available_version) for item in packages] == [
        ("zlib1g", "1:1.3.1-1+b1", "1:1.3.1-1+deb13u1"),
        ("libpve-guest-common-perl", "6.0.6", "6.0.7"),
    ]


def test_update_service_keeps_passive_reader_separate_from_button_simulation():
    class Reader:
        def list_upgradable(self, vmid=None):
            return 0, "Listing...\ncurl/stable 2 [upgradable from: 1]\n", ""
    class Simulation(Runner):
        def simulate(self, vmid=None):
            self.calls.append(vmid)
            return 0, "Inst curl [1] (2)", ""
    runner = Simulation()
    checked = UpdateService(lambda: (target(),), reader=Reader(), runner=runner)
    assert checked.check("container:107").available_count == 1
    assert runner.calls == []
    result = checked.dry_run("container:107", confirmed=True)
    assert result["success"] is True and runner.calls == [107]


def test_dry_run_accepts_same_plan_with_different_source_order():
    class Reader:
        def list_upgradable(self, vmid=None):
            return 0, "Listing...\ncurl/stable 2 [upgradable from: 1]\nopenssl/stable 4 [upgradable from: 3]\n", ""

    runner = Runner("Inst openssl [3] (4)\nInst curl [1] (2)\n")
    checked = UpdateService(lambda: (target(),), reader=Reader(), runner=runner)
    result = checked.dry_run("container:107", confirmed=True)
    assert result["success"] is True and result["safe"] is True


def test_default_allowlist_does_not_authorize_guest_targets_or_start_stopped_lxc():
    targets = make_targets(
        {"name": "pve"},
        [{"container_id": 107, "name": "running", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt"},
         {"container_id": 112, "name": "stopped", "running": False, "os_name": "Debian", "os_version": "12", "package_manager": "apt"}],
    )
    results = {item.target: item for item in targets}
    assert results["container:107"].authorized is False
    assert results["container:112"].checkable is False


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
    result = service(Runner(), (vm,)).check("vm:104")
    assert result.status == "not_checked"
    assert result.simulation_reason == "vm-guest-transport-unavailable"


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


def test_vm_simulation_never_calls_guest_runner():
    runner = Runner("Inst dangerous [1] (2)")
    vm = ProbeTarget("vm:104", "haos", 104, "Home Assistant OS", "unknown", None, True, True)
    result = service(runner, (vm,)).dry_run("vm:104", confirmed=True)
    assert result["success"] is False
    assert "transport is unavailable" in result["error"]
    assert runner.calls == []


def test_same_target_simulation_is_not_run_in_parallel():
    runner = Runner("Inst curl [1] (2)")
    checked = service(runner)
    checked._active_simulations.add("container:107")
    result = checked.dry_run("container:107", confirmed=True)
    assert result["success"] is False
    assert "already running" in result["error"]
    assert runner.calls == []
    checked._active_simulations.clear()


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
