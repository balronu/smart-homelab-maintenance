from pathlib import Path

from agent.smart_homelab_maintenance.apply_controller import AllowlistApplyController
from agent.smart_homelab_maintenance.orchestration_status import OrchestrationStatus
from agent.smart_homelab_maintenance.orchestrator import LxcOrchestrator
from agent.smart_homelab_maintenance.policy import Policy, PolicyMode
from agent.smart_homelab_maintenance.discovery_probe import ProbeState


def debian(version):
    return {"os_release": f"ID=debian\nVERSION_ID={version}\n", "apt_version": "apt 3", "dpkg_version": "dpkg 1"}


class Transport:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def probe(self, container_id):
        self.calls.append(container_id)
        return self.values[container_id]


def records():
    return [
        {"container_id": 201, "name": "debian12", "running": True},
        {"container_id": 202, "name": "debian13", "running": True},
        {"container_id": 203, "name": "ubuntu", "running": True},
        {"container_id": 204, "name": "unsupported", "running": True},
        {"container_id": 205, "name": "stopped", "running": False},
        {"vmid": 104, "name": "haos", "running": True},
    ]


def test_complete_isolated_flow_and_dynamic_events(tmp_path: Path):
    transport = Transport({
        201: debian("12"), 202: debian("13"), 203: {"os_release": "ID=ubuntu\nVERSION_ID=24.04\n", "apt_version": "apt 2", "dpkg_version": "dpkg 1"},
        204: {"os_release": "ID=alpine\nVERSION_ID=3.20\n", "apt_version": "apk", "dpkg_version": ""},
    })
    controller = AllowlistApplyController(tmp_path / "allowlist.toml", audit_path=tmp_path / "audit.log", require_root=False)
    status = OrchestrationStatus()
    orchestrator = LxcOrchestrator(controller, status)
    first = orchestrator.run(records(), policy=Policy(PolicyMode.AUTO_ELIGIBLE), transport=transport)
    assert first.apply.applied is False
    assert first.reconcile.allowlist_plan.authorized_ids == frozenset({201, 202, 203})
    assert transport.calls == [201, 202, 203, 204]
    applied = orchestrator.run(records(), policy=Policy(PolicyMode.AUTO_ELIGIBLE), transport=transport, confirmed=True)
    assert applied.apply.applied is True
    assert applied.status.authorized_container_ids == [201, 202, 203]
    assert len((tmp_path / "audit.log").read_text().splitlines()) == 1
    stopped = [item for item in records() if item.get("container_id") != 202 and item.get("vmid") != 104]
    stopped[0]["running"] = False
    after_stop = orchestrator.run(stopped, policy=Policy(PolicyMode.AUTO_ELIGIBLE), transport=transport, existing_authorized_ids={201, 202, 203})
    assert 201 not in after_stop.reconcile.allowlist_plan.authorized_ids
    assert 201 in after_stop.reconcile.allowlist_plan.removed_ids
    assert after_stop.reconcile.probes[0].state is ProbeState.STOPPED


def test_discover_only_is_a_no_guest_access_migration_default(tmp_path: Path):
    transport = Transport({201: debian("13")})
    controller = AllowlistApplyController(tmp_path / "allowlist.toml", require_root=False)
    result = LxcOrchestrator(controller).run([{"container_id": 201, "running": True}], policy=Policy(), transport=transport, confirmed=True)
    assert transport.calls == []
    assert result.apply.applied is True
    assert result.reconcile.allowlist_plan.authorized_ids == frozenset()


def test_apply_audit_failure_rolls_back_without_rights_expansion(tmp_path: Path):
    allowlist = tmp_path / "allowlist.toml"
    audit = tmp_path / "missing" / "audit.log"
    controller = AllowlistApplyController(allowlist, audit_path=audit, require_root=False)
    plan = controller.preview
    # A directory at the audit path makes the audit append fail after the
    # atomic allowlist replacement, exercising the rollback guard.
    audit.mkdir(parents=True)
    from agent.smart_homelab_maintenance.authorization import AuthorizationMode, plan_allowlist
    candidate = plan_allowlist([{"container_id": 201, "running": True, "os_name": "debian", "os_version": "13", "package_manager": "apt"}], mode=AuthorizationMode.AUTO_AUTHORIZE_SUPPORTED_RUNNING)
    result = controller.apply(candidate, confirmed=True)
    assert result.applied is False and result.error == "audit_write_failed"
    assert not allowlist.exists()
