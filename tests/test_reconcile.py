from agent.smart_homelab_maintenance.policy import Policy, PolicyMode
from agent.smart_homelab_maintenance.reconcile import reconcile
from agent.smart_homelab_maintenance.discovery_probe import ProbeState


def record(container_id, running=True):
    return {"container_id": container_id, "name": f"lxc-{container_id}", "running": running}


class Transport:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def probe(self, container_id):
        self.calls.append(container_id)
        value = self.payloads[container_id]
        if isinstance(value, Exception):
            raise value
        return value


def debian(version="13"):
    return {"os_release": f"ID=debian\nVERSION_ID={version}\n", "apt_version": "apt 3", "dpkg_version": "dpkg 1"}


def test_discover_only_is_fail_closed_and_does_not_call_transport():
    transport = Transport({201: debian()})
    result = reconcile([record(201)], policy=Policy(), transport=transport)
    assert transport.calls == []
    assert result.probes[0].state is ProbeState.UNAUTHORIZED
    assert result.allowlist_plan.authorized_ids == frozenset()


def test_discover_only_preserves_existing_manual_permission_from_inventory():
    transport = Transport({})
    result = reconcile([{"container_id": 201, "name": "lxc-201", "running": True, "os_name": "debian", "os_version": "13", "package_manager": "apt"}], policy=Policy(manual_authorized_ids=frozenset({201})), transport=transport)
    assert result.allowlist_plan.authorized_ids == frozenset({201})
    assert transport.calls == []


def test_auto_policy_is_sequential_and_authorizes_only_proven_running_lxcs():
    transport = Transport({201: debian("13"), 202: debian("12"), 203: {"os_release": "ID=alpine\nVERSION_ID=3.20\n", "apt_version": "apk", "dpkg_version": ""}, 204: RuntimeError("timeout")})
    records = [record(201), record(202), record(203), record(204), record(205, running=False)]
    result = reconcile(records, policy=Policy(PolicyMode.AUTO_ELIGIBLE), transport=transport, existing_authorized_ids={999})
    assert transport.calls == [201, 202, 203, 204]
    assert result.allowlist_plan.authorized_ids == frozenset({201, 202})
    assert 999 in result.allowlist_plan.removed_ids
    assert result.probes[-1].state is ProbeState.STOPPED


def test_manual_ids_are_not_auto_added_from_stale_or_failed_probe():
    transport = Transport({201: RuntimeError("unavailable")})
    result = reconcile([record(201)], policy=Policy(PolicyMode.AUTO_ELIGIBLE, manual_authorized_ids=frozenset({201})), transport=transport)
    assert result.allowlist_plan.authorized_ids == frozenset()


def test_vm_like_record_and_invalid_ids_never_reach_transport():
    transport = Transport({})
    result = reconcile([{"vmid": 104, "running": True}, {"container_id": "201", "running": True}], policy=Policy(PolicyMode.AUTO_ELIGIBLE), transport=transport)
    assert transport.calls == []
    assert all(probe.state is ProbeState.PROBE_FAILED for probe in result.probes)
