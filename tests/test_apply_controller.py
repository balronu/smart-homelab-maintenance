from pathlib import Path

from agent.smart_homelab_maintenance.apply_controller import AllowlistApplyController
from agent.smart_homelab_maintenance.authorization import AuthorizationMode, plan_allowlist


def plan():
    return plan_allowlist(
        [{"container_id": 201, "name": "test", "running": True, "os_name": "debian", "os_version": "13", "package_manager": "apt"}],
        mode=AuthorizationMode.AUTO_AUTHORIZE_SUPPORTED_RUNNING,
    )


def test_controller_previews_without_writing(tmp_path: Path):
    path = tmp_path / "allowlist.toml"
    result = AllowlistApplyController(path, require_root=False).apply(plan())
    assert result.applied is False
    assert not path.exists()


def test_controller_applies_atomically_only_when_confirmed(tmp_path: Path):
    path = tmp_path / "allowlist.toml"
    controller = AllowlistApplyController(path, require_root=False)
    result = controller.apply(plan(), confirmed=True)
    assert result.applied is True
    assert result.changed is True
    assert 'containers."201"' in path.read_text()
    unchanged = controller.apply(plan(), confirmed=True)
    assert unchanged.applied is True
    assert unchanged.changed is False
