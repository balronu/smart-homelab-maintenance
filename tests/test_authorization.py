from agent.smart_homelab_maintenance.authorization import (
    AuthorizationMode,
    plan_allowlist,
    render_allowlist,
)


def record(container_id, *, running=True, os_name="Debian", os_version="13", package_manager="apt"):
    return {
        "container_id": container_id,
        "name": f"lxc-{container_id}",
        "running": running,
        "os_name": os_name,
        "os_version": os_version,
        "package_manager": package_manager,
    }


def test_discover_only_never_adds_new_permissions():
    plan = plan_allowlist([record(201)], mode=AuthorizationMode.DISCOVER_ONLY)
    assert plan.authorized_ids == frozenset()
    assert plan.entries[0].reason == "supported-running-apt"


def test_auto_mode_authorizes_only_positive_running_apt_evidence():
    plan = plan_allowlist([
        record(201),
        record(202, running=False),
        record(203, os_name="Alpine"),
        record(204, package_manager=None),
    ], mode=AuthorizationMode.AUTO_AUTHORIZE_SUPPORTED_RUNNING)
    assert plan.authorized_ids == frozenset({201})
    assert {entry.reason for entry in plan.entries if not entry.authorized} == {
        "container-stopped",
        "operating-system-unsupported-or-unknown",
        "package-manager-unsupported-or-unknown",
    }


def test_stale_and_invalid_existing_permissions_are_not_retained():
    plan = plan_allowlist([record(201, running=False)], mode=AuthorizationMode.AUTO_AUTHORIZE_SUPPORTED_RUNNING, existing_authorized_ids=[201, 999999, 77])
    assert plan.authorized_ids == frozenset()
    assert plan.removed_ids == frozenset({77, 999999})


def test_render_has_only_concrete_authorized_numeric_entries():
    plan = plan_allowlist([record(201), record(202)], mode=AuthorizationMode.AUTO_AUTHORIZE_SUPPORTED_RUNNING)
    text = render_allowlist(plan)
    assert '[containers."201"]' in text
    assert '[containers."202"]' in text
    assert "*" not in text
    assert "vm:" not in text
