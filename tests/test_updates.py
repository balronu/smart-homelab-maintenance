from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.smart_homelab_maintenance.api import ApiApplication
from agent.smart_homelab_maintenance.discovery import DiscoveryService, FixtureProxmoxBackend, phase1_fixture
from agent.smart_homelab_maintenance.errors import ValidationError
from agent.smart_homelab_maintenance.jobs import JobRepository
from agent.smart_homelab_maintenance.permissions import PermissionStore
from agent.smart_homelab_maintenance.types import JobPhase, JobRequest, JobState
from agent.smart_homelab_maintenance.updates import AptCommandRunner, AptUpdateReader, GuestHelperUnavailableError, ProbeTarget, RootHelperTransport, UpdateService, _parse_apt, _parse_apt_upgradable, make_targets


def target(os_name="Debian"):
    return ProbeTarget("container:107", "fixture", 107, os_name, "12", "apt")


class Runner:
    def __init__(self, stdout="", stderr="", code=0):
        self.stdout, self.stderr, self.code = stdout, stderr, code
        self.calls = []

    def simulate(self, vmid=None):
        self.calls.append(vmid)
        return self.code, self.stdout, self.stderr

    def update(self, vmid):
        self.calls.append(("update", vmid))
        return self.code, self.stdout, self.stderr

    def probe(self, vmid):
        self.calls.append(("probe", vmid))
        return {"running": True, "supported": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt"}


class SlowUpdateRunner(Runner):
    def update(self, vmid):
        self.calls.append(("update", vmid))
        time.sleep(0.15)
        return self.code, self.stdout, self.stderr


class SlowSimulationRunner(Runner):
    def simulate(self, vmid=None):
        self.calls.append(vmid)
        time.sleep(0.15)
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
    separately_authorized = make_targets({"name": "pve"}, [{"container_id": 108, "name": "fixture", "running": True}], {
        "container:108": {"simulation_authorized": True, "update_authorized": True, "os_name": "Ubuntu", "os_version": "24.04", "package_manager": "apt"},
    })[1]
    assert separately_authorized.authorized is True and separately_authorized.update_authorized is True
    vm = make_targets({"name": "pve"}, [], virtual_machines=[{"vmid": 104, "name": "haos"}])[1]
    result = service(Runner(), (vm,)).check("vm:104")
    assert result.status == "not_checked"
    assert result.simulation_reason == "vm-guest-transport-unavailable"


def test_update_check_distinguishes_missing_lxc_helper_from_authorization():
    def unavailable(_payload):
        raise OSError("socket missing")

    transport = RootHelperTransport(exchange=unavailable)
    reader = AptUpdateReader(guest_transport=transport)
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True)
    checked = UpdateService(lambda: (authorized,), reader=reader)
    result = checked.check("container:107")
    assert result.status == "unknown"
    assert result.supported is True
    assert result.error == "LXC simulation helper is unavailable"
    assert result.simulation_reason == "helper-unavailable"


def test_permission_grant_probes_unknown_discovery_before_writing_policy(tmp_path):
    store = PermissionStore(tmp_path / "policy.toml")
    runner = Runner()
    service = UpdateService(
        lambda: (ProbeTarget("container:102", "cloudflared", 102, "unknown", "unknown", None, False, True),),
        runner=runner,
        permission_store=store,
    )
    result = service.set_permissions("container:102", simulation_authorized=True, update_authorized=False, confirmed=True)
    assert result["simulation_authorized"] is True
    assert ("probe", 102) in runner.calls
    assert store.read()["102"]["os_name"] == "Debian"


def test_permission_change_invalidates_cached_update_authorization(tmp_path):
    store = PermissionStore(tmp_path / "policy.toml")
    runner = Runner("0 upgraded, 0 newly installed, 0 to remove.")
    service = UpdateService(
        lambda: (ProbeTarget("container:102", "cloudflared", 102, "Debian", "12", "apt", False, True),),
        runner=runner,
        permission_store=store,
    )
    assert service.check("container:102").status == "unauthorized"
    service.set_permissions("container:102", simulation_authorized=True, update_authorized=False, confirmed=True)
    assert service.check("container:102").status == "current"


def test_permission_metadata_is_reused_for_followup_update_checks(tmp_path):
    store = PermissionStore(tmp_path / "policy.toml")
    store.set_permissions(
        "container:102",
        simulation_authorized=True,
        update_authorized=False,
        metadata={"os_name": "Debian", "os_version": "12", "package_manager": "apt"},
    )
    service = UpdateService(
        lambda: (ProbeTarget("container:102", "zigbee2mqtt", 102, "unknown", "unknown", None, False, True),),
        runner=Runner("0 upgraded, 0 newly installed, 0 to remove."),
        permission_store=store,
    )
    result = service.check("container:102")
    data = result.as_dict()
    assert result.status == "current"
    assert data["authorized"] is True and data["simulation_authorized"] is True
    assert result.os_name == "Debian" and result.package_manager == "apt"


def test_permission_revoke_does_not_require_a_fresh_eligibility_probe(tmp_path):
    store = PermissionStore(tmp_path / "policy.toml")
    store.set_permissions("container:102", simulation_authorized=True, update_authorized=False, metadata={"os_name": "Debian", "os_version": "12", "package_manager": "apt"})

    class NoProbe:
        def probe(self, _vmid):
            raise AssertionError("revoke must not probe")

    service = UpdateService(
        lambda: (ProbeTarget("container:102", "cloudflared", 102, "unknown", "unknown", None, True, True),),
        runner=NoProbe(),
        permission_store=store,
    )
    result = service.set_permissions("container:102", simulation_authorized=False, update_authorized=False, confirmed=True)
    assert result["simulation_authorized"] is False
    assert store.read()["102"]["os_name"] == "Debian"


def test_helper_unavailable_error_is_not_a_generic_os_error():
    transport = RootHelperTransport(exchange=lambda _payload: (_ for _ in ()).throw(OSError("missing")))
    with pytest.raises(GuestHelperUnavailableError, match="helper is unavailable"):
        transport.read(107)


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


def test_real_update_requires_explicit_permission_fresh_plan_and_confirmation():
    runner = Runner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    with tempfile.TemporaryDirectory() as directory:
        jobs = JobRepository(str(Path(directory) / "jobs.sqlite"))
        checked = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=jobs)
        result = checked.check("container:107")
        assert result.update_authorized is True and result.update_supported is True
        # Validation is deliberately raised before any guest call.
        runner.calls.clear()
        with pytest.raises(ValidationError, match="explicit.*confirmation"):
            checked.execute_update("container:107", confirmed=False, plan_digest=result.plan_digest)
        accepted = checked.execute_update("container:107", confirmed=True, install_confirmed=True, plan_digest=result.plan_digest)
        assert accepted["success"] is True and accepted["accepted"] is True and accepted["status"] == "running"
        for _ in range(50):
            if jobs.get(accepted["job_id"])["state"] == "succeeded":
                break
            time.sleep(0.01)
        assert jobs.get(accepted["job_id"])["state"] == "succeeded"
        assert ("update", 107) in runner.calls
        jobs.close()


def test_real_update_is_disabled_or_rejected_for_unauthorized_and_vm_targets():
    runner = Runner("Inst curl [1] (2)")
    disabled = UpdateService(lambda: (target(),), runner=runner, execution_enabled=False)
    assert disabled.execute_update("container:107", confirmed=True, install_confirmed=True, plan_digest="x")["error"] == "update execution is disabled"
    vm = ProbeTarget("vm:104", "haos", 104, "Home Assistant OS", "unknown", None, True, True, True)
    enabled = UpdateService(lambda: (vm,), runner=runner, execution_enabled=True)
    result = enabled.execute_update("vm:104", confirmed=True, install_confirmed=True, plan_digest="x")
    assert result["success"] is False and "only authorized LXC" in result["error"]
    assert runner.calls == []


def test_api_execute_returns_structured_update_result_after_fresh_check():
    runner = Runner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    with tempfile.TemporaryDirectory() as directory:
        repo = JobRepository(str(Path(directory) / "jobs.sqlite"))
        updates = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=repo)
        api = ApiApplication(DiscoveryService(FixtureProxmoxBackend(phase1_fixture())), repo, updates=updates, read_token="token")
        headers = {"Authorization": "Bearer token"}
        _, check_body = api.handle("GET", "/api/v1/updates/container:107", headers=headers)
        digest = check_body["data"]["plan_digest"]
        status, body = api.handle("POST", "/api/v1/updates/container:107/execute", headers=headers, body=(f'{{"confirm":true,"install_confirmed":true,"plan_digest":"{digest}"}}').encode())
        assert status == 200 and body["data"]["success"] is True and body["data"]["accepted"] is True
        assert body["data"]["status"] == "running"
        for _ in range(50):
            if repo.get(body["data"]["job_id"])["state"] == "succeeded":
                break
            time.sleep(0.01)
        assert repo.get(body["data"]["job_id"])["state"] == "succeeded"
        repo.close()


def test_api_permission_endpoint_is_explicit_and_separates_simulation_from_update():
    runner = Runner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", False, True, False)
    with tempfile.TemporaryDirectory() as directory:
        store = PermissionStore(Path(directory) / "allowlist.toml")
        updates = UpdateService(lambda: (authorized,), runner=runner, permission_store=store)
        repo = JobRepository(str(Path(directory) / "jobs.sqlite"))
        api = ApiApplication(DiscoveryService(FixtureProxmoxBackend(phase1_fixture())), repo, updates=updates, read_token="token")
        headers = {"Authorization": "Bearer token"}
        status, _ = api.handle("POST", "/api/v1/updates/container:107/permissions", headers=headers, body=b'{"confirm":true,"simulation_authorized":true,"update_authorized":false}')
        assert status == 200
        assert updates.check("container:107", force=True).authorized is True
        assert updates.check("container:107", force=True).as_dict()["simulation_authorized"] is True
        status, _ = api.handle("POST", "/api/v1/updates/container:107/permissions", headers=headers, body=b'{"confirm":true,"simulation_authorized":false,"update_authorized":false}')
        assert status == 200
        assert updates.check("container:107", force=True).as_dict()["authorized"] is False
        status, _ = api.handle("POST", "/api/v1/updates/container:107/permissions", headers=headers, body=b'{"confirm":true,"simulation_authorized":false,"update_authorized":true}')
        assert status == 400
        repo.close()


def test_vm_simulation_never_calls_guest_runner():
    runner = Runner("Inst dangerous [1] (2)")
    vm = ProbeTarget("vm:104", "haos", 104, "Home Assistant OS", "unknown", None, True, True)
    result = service(runner, (vm,)).dry_run("vm:104", confirmed=True)
    assert result["success"] is False
    assert "transport is unavailable" in result["error"]
    assert runner.calls == []


def test_all_vm_targets_are_monitoring_only_and_never_reach_any_runner():
    runner = Runner("Inst dangerous [1] (2)")
    targets = (
        ProbeTarget("vm:104", "haos", 104, "Home Assistant OS", "unknown", None, False, False),
        ProbeTarget("vm:106", "pbs", 106, "Proxmox Backup Server", "3", "apt", False, False),
    )
    checked = service(runner, targets)
    for target_id in ("vm:104", "vm:106"):
        result = checked.dry_run(target_id, confirmed=True)
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
        status, body = api.handle("POST", "/api/v1/updates/container:107/execute", headers=headers, body=b'{"confirm":true}')
        assert status == 400 and body["error"]["code"] == "invalid_request"
        repo.close()


def test_execute_requires_a_separate_installation_confirmation():
    runner = Runner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    checked = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True)
    plan = checked.check("container:107")
    with pytest.raises(ValidationError, match="both required"):
        checked.execute_update("container:107", confirmed=True, plan_digest=plan.plan_digest)
    assert runner.calls == [107]


def test_execute_revalidates_simulation_before_mutation_and_persists_job(tmp_path):
    runner = Runner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    checked = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=jobs)
    plan = checked.check("container:107")
    result = checked.execute_update("container:107", confirmed=True, install_confirmed=True, plan_digest=plan.plan_digest)
    assert result["success"] is True and result["accepted"] is True and result["job_id"]
    for _ in range(50):
        if jobs.get(result["job_id"])["state"] == "succeeded":
            break
        time.sleep(0.01)
    stored = jobs.get(result["job_id"])
    assert stored["state"] == "succeeded"
    assert [call for call in runner.calls if call == 107] == [107, 107, 107]
    jobs.close()


def test_execute_returns_before_slow_update_and_blocks_duplicate_click(tmp_path):
    runner = SlowUpdateRunner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    checked = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=jobs)
    plan = checked.check("container:107")
    started = time.monotonic()
    accepted = checked.execute_update("container:107", confirmed=True, install_confirmed=True, plan_digest=plan.plan_digest)
    elapsed = time.monotonic() - started
    assert elapsed < 0.1
    assert accepted["accepted"] is True and accepted["status"] == "running"
    duplicate = checked.execute_update("container:107", confirmed=True, install_confirmed=True, plan_digest=plan.plan_digest)
    assert duplicate["success"] is False and "another update is active" in duplicate["error"]
    for _ in range(50):
        if jobs.get(accepted["job_id"])["state"] == "succeeded":
            break
        time.sleep(0.01)
    assert jobs.get(accepted["job_id"])["state"] == "succeeded"
    jobs.close()


def test_reconciled_historical_job_allows_new_confirmed_attempt(tmp_path):
    runner = Runner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    checked = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=jobs)
    plan = checked.check("container:107")
    historical = jobs.create(JobRequest(
        target="container:107", operation="update", expected_version=None,
        idempotency_key=f"container:107:{plan.plan_digest}", confirmation_hash=plan.plan_digest,
    ))
    jobs.transition(historical, JobState.PREFLIGHT, phase=JobPhase.PREFLIGHT)
    jobs.transition(historical, JobState.MANUAL_RECOVERY, phase=JobPhase.RECOVERY)
    jobs.transition(historical, JobState.RECONCILED_LEGACY_STATE_VERIFIED, phase=JobPhase.RECOVERY)
    accepted = checked.execute_update(
        "container:107", confirmed=True, install_confirmed=True,
        plan_digest=plan.plan_digest, attempt_id="attempt-new-12345678",
    )
    assert accepted["success"] is True and accepted["job_id"] != historical
    for _ in range(50):
        if jobs.get(accepted["job_id"])["state"] == JobState.SUCCEEDED:
            break
        time.sleep(0.01)
    assert jobs.count() == 2
    assert jobs.get(historical)["state"] == JobState.RECONCILED_LEGACY_STATE_VERIFIED
    jobs.close()


def test_identical_attempt_retry_replays_same_job_without_second_job(tmp_path):
    runner = SlowUpdateRunner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    checked = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=jobs)
    plan = checked.check("container:107")
    request = dict(confirmed=True, install_confirmed=True, plan_digest=plan.plan_digest, attempt_id="attempt-retry-12345678")
    first = checked.execute_update("container:107", **request)
    retry = checked.execute_update("container:107", **request)
    assert first["success"] is True and retry["replayed"] is True
    assert retry["job_id"] == first["job_id"]
    assert jobs.count() == 1
    for _ in range(50):
        if jobs.get(first["job_id"])["state"] == JobState.SUCCEEDED:
            break
        time.sleep(0.01)
    assert [call for call in runner.calls if call == ("update", 107)] == [("update", 107)]
    jobs.close()


def test_api_execute_persists_and_replays_attempt_identity(tmp_path):
    runner = Runner("Inst curl [7.0] (7.1)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    updates = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=jobs)
    api = ApiApplication(DiscoveryService(FixtureProxmoxBackend(phase1_fixture())), jobs, updates=updates, read_token="token")
    plan = updates.check("container:107")
    body = {"confirm": True, "install_confirmed": True, "plan_digest": plan.plan_digest, "attempt_id": "attempt-api-12345678"}
    headers = {"Authorization": "Bearer token"}
    import json
    status, first = api.handle("POST", "/api/v1/updates/container:107/execute", headers=headers, body=json.dumps(body).encode())
    status_retry, retry = api.handle("POST", "/api/v1/updates/container:107/execute", headers=headers, body=json.dumps(body).encode())
    assert status == 200 and status_retry == 200
    assert first["data"]["job_id"] == retry["data"]["job_id"]
    assert retry["data"]["replayed"] is True
    assert jobs.count() == 1
    for _ in range(50):
        if jobs.get(first["data"]["job_id"])["state"] in {JobState.SUCCEEDED, JobState.FAILED, JobState.BLOCKED, JobState.MANUAL_RECOVERY}:
            break
        time.sleep(0.01)
    jobs.close()


def test_changed_update_plan_requires_new_confirmation_and_creates_no_job(tmp_path):
    runner = Runner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    updates = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=jobs)
    plan = updates.check("container:107")
    result = updates.execute_update(
        "container:107", confirmed=True, install_confirmed=True,
        plan_digest="0" * 64, attempt_id="attempt-stale-12345678",
    )
    assert result["success"] is False and "confirmation is stale" in result["error"]
    assert jobs.count() == 0
    assert not any(call == ("update", 107) for call in runner.calls)
    jobs.close()


def test_duplicate_without_attempt_identity_is_structured_conflict(tmp_path):
    runner = Runner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    updates = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=jobs)
    plan = updates.check("container:107")
    jobs.create(JobRequest(
        target="container:107", operation="update", expected_version=None,
        idempotency_key=f"container:107:{plan.plan_digest}", confirmation_hash=plan.plan_digest,
    ))
    api = ApiApplication(DiscoveryService(FixtureProxmoxBackend(phase1_fixture())), jobs, updates=updates, read_token="token")
    import json
    status, body = api.handle("POST", "/api/v1/updates/container:107/execute", headers={"Authorization": "Bearer token"}, body=json.dumps({"confirm": True, "install_confirmed": True, "plan_digest": plan.plan_digest}).encode())
    assert status == 409
    assert body["error"]["code"] == "duplicate_job"
    assert jobs.count() == 1
    jobs.close()


def test_execute_returns_before_slow_final_preflight(tmp_path):
    runner = SlowSimulationRunner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    checked = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=jobs)
    plan = checked.check("container:107")
    started = time.monotonic()
    accepted = checked.execute_update("container:107", confirmed=True, install_confirmed=True, plan_digest=plan.plan_digest)
    assert time.monotonic() - started < 0.1
    assert accepted["accepted"] is True and accepted["status"] == "running"
    for _ in range(80):
        if jobs.get(accepted["job_id"])["state"] == "succeeded":
            break
        time.sleep(0.01)
    assert jobs.get(accepted["job_id"])["state"] == "succeeded"
    jobs.close()


def test_preflight_timeout_is_blocked_without_manual_recovery_or_update(tmp_path):
    class InspectTimeoutRunner(Runner):
        def inspect(self, vmid):
            self.calls.append(("inspect", vmid))
            raise TimeoutError("helper inspection exceeded timeout")

    runner = InspectTimeoutRunner("Inst curl [1] (2)")
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    updates = UpdateService(lambda: (authorized,), runner=runner, execution_enabled=True, jobs=jobs)
    plan = updates.check("container:107")
    accepted = updates.execute_update(
        "container:107", confirmed=True, install_confirmed=True, plan_digest=plan.plan_digest,
        attempt_id="preflight-timeout-1",
    )
    assert accepted["accepted"] is True
    for _ in range(80):
        if jobs.get(accepted["job_id"])["state"] == JobState.BLOCKED:
            break
        time.sleep(0.01)
    job = jobs.get(accepted["job_id"])
    assert job["state"] == JobState.BLOCKED
    assert job["phase"] == JobPhase.PREFLIGHT.value
    assert job["error_code"] == "preflight_helper_timeout"
    assert not any(call == ("update", 107) for call in runner.calls)
    jobs.close()


def test_cancel_is_persistent_before_mutation_and_api_requires_confirmation(tmp_path):
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    request = __import__("agent.smart_homelab_maintenance.types", fromlist=["JobRequest"]).JobRequest(
        target="container:107", operation="update", expected_version=None,
        idempotency_key="cancel-before-run", confirmation_hash="a" * 64)
    job_id = jobs.create(request)
    jobs.transition(job_id, __import__("agent.smart_homelab_maintenance.types", fromlist=["JobState", "JobPhase"]).JobState.PREFLIGHT,
                    phase=__import__("agent.smart_homelab_maintenance.types", fromlist=["JobPhase"]).JobPhase.PREFLIGHT)
    updates = UpdateService(lambda: (target(),), runner=Runner(), execution_enabled=True, jobs=jobs)
    with pytest.raises(ValidationError, match="confirmation"):
        updates.cancel_job(job_id, confirmed=False)
    result = updates.cancel_job(job_id, confirmed=True)
    assert result["accepted"] is True and result["state"] == "cancelled"
    assert jobs.get(job_id)["cancel_requested"] == 1
    assert jobs.has_unresolved_target("container:107") is False
    jobs.close()


def test_running_cancellation_is_refused_and_manual_recovery_blocks_new_mutation(tmp_path):
    jobs = JobRepository(str(tmp_path / "jobs.sqlite"))
    request = __import__("agent.smart_homelab_maintenance.types", fromlist=["JobRequest"]).JobRequest(
        target="container:107", operation="update", expected_version=None,
        idempotency_key="running-job", confirmation_hash="b" * 64)
    job_id = jobs.create(request)
    types = __import__("agent.smart_homelab_maintenance.types", fromlist=["JobState", "JobPhase"])
    jobs.transition(job_id, types.JobState.PREFLIGHT, phase=types.JobPhase.PREFLIGHT)
    jobs.transition(job_id, types.JobState.RUNNING, phase=types.JobPhase.EXECUTION)
    authorized = ProbeTarget("container:107", "fixture", 107, "Debian", "12", "apt", True, True, True)
    updates = UpdateService(lambda: (authorized,), runner=Runner("Inst curl [1] (2)"), execution_enabled=True, jobs=jobs)
    result = updates.cancel_job(job_id, confirmed=True)
    assert result == {"accepted": False, "state": types.JobState.RUNNING, "reason": "running_cancellation_not_safe"}
    assert jobs.get(job_id)["state"] == "running"
    jobs.transition(job_id, types.JobState.MANUAL_RECOVERY, phase=types.JobPhase.RECOVERY, message="manual recovery required")
    blocked = updates.execute_update("container:107", confirmed=True, install_confirmed=True, plan_digest="anything")
    assert blocked["status"] == "manual_recovery_required"
    jobs.close()
