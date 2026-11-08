from pathlib import Path

import pytest

from agent.smart_homelab_maintenance.permissions import PermissionStore


def test_permission_store_atomically_grants_and_revokes_separate_rights(tmp_path: Path):
    path = tmp_path / "lxc-apt-allowlist.toml"
    store = PermissionStore(path)
    result = store.set_permissions(
        "container:110",
        simulation_authorized=True,
        update_authorized=False,
        metadata={"os_name": "Debian", "os_version": "12", "package_manager": "apt"},
    )
    assert result["simulation_authorized"] is True
    assert store.read()["110"]["update_authorized"] is False
    store.set_permissions(
        "container:110",
        simulation_authorized=False,
        update_authorized=False,
        metadata={"os_name": "Debian", "os_version": "12", "package_manager": "apt"},
    )
    assert store.read()["110"]["simulation_authorized"] is False
    assert path.stat().st_mode & 0o077 == 0


def test_permission_store_rejects_insecure_existing_file(tmp_path: Path):
    path = tmp_path / "allowlist.toml"
    path.write_text('[containers."110"]\nsimulation_authorized = true\n', encoding="utf-8")
    path.chmod(0o644)
    with pytest.raises(Exception, match="writable"):
        PermissionStore(path).read()

