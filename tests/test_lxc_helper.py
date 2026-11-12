from __future__ import annotations

import importlib.util
import os
import socket
import stat
from types import SimpleNamespace
from pathlib import Path

import pytest

from agent.smart_homelab_maintenance.updates import LXC_HELPER_SOCKET, RootHelperTransport
from agent.smart_homelab_maintenance.server import load_runtime_config


HELPER_PATH = Path(__file__).parents[1] / "scripts" / "smh-lxc-apt-helper.py"
SPEC = importlib.util.spec_from_file_location("smh_lxc_apt_helper", HELPER_PATH)
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)

DISCOVERY_PATH = Path(__file__).parents[1] / "scripts" / "smh-lxc-discovery.py"
DISCOVERY_SPEC = importlib.util.spec_from_file_location("smh_lxc_discovery", DISCOVERY_PATH)
assert DISCOVERY_SPEC and DISCOVERY_SPEC.loader
discovery = importlib.util.module_from_spec(DISCOVERY_SPEC)
DISCOVERY_SPEC.loader.exec_module(discovery)


def test_helper_builds_only_fixed_read_and_simulation_commands() -> None:
    read = helper.build_argv(101, "read")
    simulate = helper.build_argv(101, "simulate")
    assert read == ["/usr/sbin/pct", "exec", "101", "--", "/usr/bin/apt", "list", "--upgradable"]
    assert simulate == [
        "/usr/sbin/pct", "exec", "101", "--", "/usr/bin/apt-get", "--simulate",
        "--no-remove", "-o", "Debug::NoLocking=true", "upgrade",
    ]
    assert all("install" not in item and item != "update" for item in read + simulate)


def test_helper_inspection_is_fixed_read_only_and_bounded() -> None:
    assert helper.build_inspect_argv(101, "packages") == [
        "/usr/sbin/pct", "exec", "101", "--", "/usr/bin/dpkg-query", "-W",
        "-f=${Package}\\t${Version}\\n",
    ]
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        if argv[1] == "status":
            return 0, "status: running\n", ""
        return 0, "demo\t1.0\n", ""

    response = helper.handle({"container_id": 101, "operation": "inspect"}, allowed_ids={101}, run=run)
    assert response["ok"] is True
    assert len(calls) == 11
    assert all(call[:4] == ["/usr/sbin/pct", "exec", "101", "--"] for call in calls[1:])
    assert all("apt-get" not in call and "install" not in call for call in calls[1:])


@pytest.mark.parametrize("name", ["apt_lock", "apt_archives_lock", "dpkg_lock", "dpkg_frontend_lock"])
def test_helper_lock_inspection_uses_kernel_lock_table_without_fuser(name: str) -> None:
    command = helper.build_inspect_argv(101, name)
    assert command[:4] == ["/usr/sbin/pct", "exec", "101", "--"]
    assert command[4:7] == ["/bin/sh", "-c", command[6]]
    script = command[6]
    assert "/proc/locks" in script
    assert "/usr/bin/fuser" not in script
    assert "/usr/bin/stat -c '%D %i'" in script
    assert "exit 2" in script


def test_helper_inspection_preserves_unknown_kernel_lock_result() -> None:
    def run(argv, **_kwargs):
        if argv[1] == "status":
            return 0, "status: running\n", ""
        return (2 if "/var/lib/apt/lists/lock" in argv else 1), "", ""

    response = helper.handle({"container_id": 101, "operation": "inspect"}, allowed_ids={101}, run=run)
    assert response["ok"] is True
    assert response["observations"]["apt_lock"]["returncode"] == 2


def test_helper_update_is_two_fixed_phases_and_requires_separate_permission() -> None:
    update = helper.build_argv(101, "update")
    assert update == ["/usr/sbin/pct", "exec", "101", "--", "/usr/bin/apt-get", "update"]
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        if argv[1] == "status":
            return 0, "status: running\n", ""
        return 0, "ok\n", ""

    denied = helper.handle({"container_id": 101, "operation": "update"}, allowed_ids={101}, update_ids=set(), run=run)
    assert denied["error"]["code"] == "update_not_authorized" and calls == []
    response = helper.handle({"container_id": 101, "operation": "update"}, allowed_ids={101}, update_ids={101}, run=run)
    assert response["ok"] is True
    assert [calls[0][1], calls[1][-1], calls[2][-1]] == ["status", "update", "upgrade"]
    assert [step["name"] for step in response["steps"]] == ["apt-update", "apt-upgrade"]


@pytest.mark.parametrize(
    "payload",
    [
        {"container_id": "101", "operation": "read"},
        {"container_id": 101, "operation": "exec"},
        {"container_id": 101, "operation": "read", "command": "apt update"},
        {"container_id": 999, "operation": "read"},
        {"container_id": True, "operation": "read"},
    ],
)
def test_helper_rejects_parameter_injection_and_unallowlisted_targets(payload) -> None:
    response = helper.handle(payload, allowed_ids={101})
    assert response["ok"] is False
    assert response["error"]["code"] in {"invalid_request", "invalid_container", "operation_not_allowed", "container_not_allowed"}


def test_helper_refuses_stopped_container_without_guest_command() -> None:
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        return 0, "status: stopped\n", ""

    response = helper.handle({"container_id": 101, "operation": "read"}, allowed_ids={101}, run=run)
    assert response == {"ok": False, "error": {"code": "not_running", "message": "stopped containers are never started or probed"}}
    assert len(calls) == 1 and calls[0] == ["/usr/sbin/pct", "status", "101"]


def test_helper_probe_proves_running_debian_and_apt_without_allowlist() -> None:
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        if argv[1] == "status":
            return 0, "status: running\n", ""
        if argv[-2:] == ["/usr/bin/cat", "/etc/os-release"]:
            return 0, 'ID=debian\nVERSION_ID="12"\n', ""
        return 0, "", ""

    result = helper.handle({"container_id": 102, "operation": "probe"}, allowed_ids=set(), run=run)
    assert result["ok"] is True
    assert result["os_name"] == "Debian" and result["package_manager"] == "apt"
    assert calls == [
        ["/usr/sbin/pct", "status", "102"],
        ["/usr/sbin/pct", "exec", "102", "--", "/usr/bin/cat", "/etc/os-release"],
        ["/usr/sbin/pct", "exec", "102", "--", "/usr/bin/test", "-x", "/usr/bin/apt-get"],
        ["/usr/sbin/pct", "exec", "102", "--", "/usr/bin/test", "-x", "/usr/bin/apt"],
    ]


def test_helper_probe_fails_closed_for_unsupported_os() -> None:
    def run(argv, **_kwargs):
        if argv[1] == "status":
            return 0, "status: running\n", ""
        return 0, "ID=alpine\nVERSION_ID=3.20\n", ""

    result = helper.handle({"container_id": 102, "operation": "probe"}, allowed_ids=set(), run=run)
    assert result["ok"] is False and result["error"]["code"] == "unsupported_os"


def test_helper_returns_guest_failure_without_turning_it_into_success() -> None:
    def run(argv, **_kwargs):
        if argv[1] == "status":
            return 0, "status: running\n", ""
        return 100, "", "apt failed"

    response = helper.handle({"container_id": 101, "operation": "simulate"}, allowed_ids={101}, run=run)
    assert response["ok"] is False and response["returncode"] == 100


def test_helper_timeout_is_explicit() -> None:
    def run(_argv, **_kwargs):
        raise helper.HelperError("timeout", "fixed guest operation timed out")

    response = helper.handle({"container_id": 101, "operation": "read"}, allowed_ids={101}, run=run)
    assert response["ok"] is False and response["error"]["code"] == "timeout"


def test_allowlist_requires_root_safe_file_and_filters_metadata(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.toml"
    allowlist.write_text(
        '[containers."101"]\nauthorized = true\nos_name = "Debian"\nos_version = "13"\npackage_manager = "apt"\n'
        '[containers."102"]\nauthorized = false\nos_name = "Debian"\nos_version = "13"\npackage_manager = "apt"\n',
        encoding="utf-8",
    )
    allowlist.chmod(0o600)
    assert helper._load_allowlist(allowlist) == {101}


def test_policy_socket_operations_preserve_root_only_policy_and_split_rights(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.toml"
    allowlist.write_text(
        '[containers."110"]\nauthorized = true\nos_name = "Debian"\nos_version = "12"\npackage_manager = "apt"\n',
        encoding="utf-8",
    )
    allowlist.chmod(0o600)
    read = helper.handle_policy({"operation": "policy_read"}, allowlist)
    assert read["entries"]["110"]["authorized"] is True
    result = helper.handle_policy({
        "operation": "policy_set", "target": "container:110",
        "simulation_authorized": True, "update_authorized": False,
        "metadata": {"os_name": "Debian", "os_version": "12", "package_manager": "apt"},
        "confirm": True,
    }, allowlist)
    assert result["data"]["simulation_authorized"] is True
    assert helper._load_permissions(allowlist) == ({110}, set())
    assert allowlist.stat().st_uid == 0 or allowlist.stat().st_uid == os.getuid()
    assert allowlist.stat().st_mode & 0o077 == 0


def test_policy_socket_rejects_update_without_simulation(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.toml"
    allowlist.write_text("# empty\n", encoding="utf-8")
    allowlist.chmod(0o600)
    with pytest.raises(helper.HelperError, match="requires simulation"):
        helper.handle_policy({
            "operation": "policy_set", "target": "container:110",
            "simulation_authorized": False, "update_authorized": True,
            "metadata": {}, "confirm": True,
        }, allowlist)


def test_policy_apply_replaces_complete_candidate_atomically_without_update_grants(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.toml"
    allowlist.write_text('[containers."999"]\nauthorized = true\nos_name = "Debian"\nos_version = "12"\npackage_manager = "apt"\n', encoding="utf-8")
    allowlist.chmod(0o600)
    result = helper.handle_policy({
        "operation": "policy_apply", "confirm": True,
        "entries": {"101": {"authorized": True, "simulation_authorized": True,
                              "update_authorized": False, "os_name": "Debian",
                              "os_version": "12", "package_manager": "apt"}},
    }, allowlist)
    assert result["data"]["authorized_ids"] == [101]
    assert helper._load_permissions(allowlist) == ({101}, set())


def test_helper_rejects_malformed_status() -> None:
    response = helper.handle(
        {"container_id": 101, "operation": "read"},
        allowed_ids={101},
        run=lambda _argv, **_kwargs: (0, "status: running\nextra\n", ""),
    )
    assert response["ok"] is False and response["error"]["code"] == "not_running"


def test_root_transport_uses_fixed_unix_socket_and_json_protocol() -> None:
    calls = []

    def exchange(payload):
        calls.append(payload)
        return b'{"ok":true,"stdout":"Listing...\\n","stderr":""}\n'

    transport = RootHelperTransport(exchange=exchange)
    assert transport.read(101) == (0, "Listing...\n", "")
    assert calls == [b'{"container_id":101,"operation":"read"}\n']
    assert transport.socket_path == LXC_HELPER_SOCKET


def test_root_transport_probe_uses_only_probe_operation() -> None:
    calls = []

    def exchange(payload):
        calls.append(payload)
        return b'{"ok":true,"operation":"probe","container_id":102,"running":true,"supported":true,"os_name":"Debian","os_version":"12","package_manager":"apt"}\n'

    transport = RootHelperTransport(exchange=exchange)
    result = transport.probe(102)
    assert result["supported"] is True
    assert calls == [b'{"container_id":102,"operation":"probe"}\n']


def test_root_transport_rejects_non_fixed_socket_path() -> None:
    with pytest.raises(ValueError):
        RootHelperTransport(socket_path="/tmp/helper.sock")


def test_helper_is_opt_in_and_disabled_by_default(tmp_path: Path) -> None:
    config = tmp_path / "agent.toml"
    config.write_text(
        'listen_host = "127.0.0.1"\nlisten_port = 48128\n'
        'certificate = "/tmp/cert"\nprivate_key = "/tmp/key"\n'
        'proxmox_url = "https://pve.lan:8006"\nproxmox_node = "pve"\n'
        f'state_directory = "{tmp_path / "state"}"\n',
        encoding="utf-8",
    )
    assert load_runtime_config(config).lxc_helper_enabled is False
    config.write_text(config.read_text(encoding="utf-8") + "lxc_helper_enabled = true\n", encoding="utf-8")
    assert load_runtime_config(config).lxc_helper_enabled is True
    config.write_text(config.read_text(encoding="utf-8").replace("lxc_helper_enabled = true", 'lxc_helper_enabled = "false"'), encoding="utf-8")
    with pytest.raises(ValueError, match="lxc_helper_enabled must be boolean"):
        load_runtime_config(config)


def test_socket_policy_requires_exact_agent_uid_and_per_request_allowlist() -> None:
    source = HELPER_PATH.read_text(encoding="utf-8")
    assert "SO_PEERCRED" in source
    assert "pwd.getpwnam(EXPECTED_CLIENT_USER)" in source
    assert "_load_permissions(self.server.allowlist_path)" in source
    assert "self.server.allowed_ids" not in source
    assert "policy_read" in source and "policy_set" in source


def test_peer_credentials_reject_wrong_uid(monkeypatch) -> None:
    class FakeSocket:
        def getsockopt(self, *_args):
            import struct
            return struct.pack("3i", 1, 424242, 1)

    monkeypatch.setattr(helper.pwd, "getpwnam", lambda _name: type("Pw", (), {"pw_uid": 1234})())
    with pytest.raises(helper.HelperError, match="not authorized"):
        helper._require_agent_peer(FakeSocket())


def test_peer_credentials_accept_exact_uid(monkeypatch) -> None:
    class FakeSocket:
        def getsockopt(self, *_args):
            import struct
            return struct.pack("3i", 1, 1234, 1)

    monkeypatch.setattr(helper.pwd, "getpwnam", lambda _name: type("Pw", (), {"pw_uid": 1234})())
    helper._require_agent_peer(FakeSocket())


def test_helper_uses_bounded_streaming_process_contract() -> None:
    source = HELPER_PATH.read_text(encoding="utf-8")
    assert "selectors.DefaultSelector" in source
    assert "MAX_OUTPUT_BYTES" in source
    assert "COMMAND_TIMEOUT_SECONDS" in source


def test_helper_documents_toc_tou_safe_failure() -> None:
    response = helper.handle(
        {"container_id": 101, "operation": "read"},
        allowed_ids={101},
        run=lambda argv, **_kwargs: (1, "", "container '101' not running"),
    )
    assert response["ok"] is False
    assert response["error"]["code"] == "status_failed"


def test_helper_service_is_root_scoped_and_not_a_general_pct_service() -> None:
    unit = (Path(__file__).parents[1] / "scripts" / "smart-homelab-maintenance-lxc-helper.service").read_text(encoding="utf-8")
    assert "User=root" in unit
    assert "Group=root" in unit
    assert "NoNewPrivileges=true" not in unit
    assert "ExecStart=/usr/libexec/smart-homelab-maintenance/lxc-apt-helper --serve" in unit
    assert "ExecStart=/usr/sbin/pct" not in unit
    assert "NOPASSWD" not in unit
    assert "ReadWritePaths=/etc/smart-homelab-maintenance\n" in unit
    assert "ReadOnlyPaths=/etc/smart-homelab-maintenance/lxc-apt-allowlist.toml" not in unit


def test_policy_write_requires_private_directory_and_cleans_temp_file(tmp_path: Path) -> None:
    policy_dir = tmp_path / "policy"
    policy_dir.mkdir(mode=0o700)
    allowlist = policy_dir / "allowlist.toml"
    helper._write_policy_entries(allowlist, {"101": {"simulation_authorized": True}})
    assert allowlist.read_text(encoding="utf-8").startswith("# Managed by")
    assert allowlist.stat().st_mode & 0o077 == 0
    assert not list(policy_dir.glob(".allowlist.toml.*"))


def test_policy_write_rejects_insecure_or_symlinked_directory(tmp_path: Path) -> None:
    insecure = tmp_path / "insecure"
    insecure.mkdir(mode=0o755)
    insecure.chmod(0o755)
    with pytest.raises(helper.HelperError, match="directory"):
        helper._write_policy_entries(insecure / "allowlist.toml", {})
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(helper.HelperError, match="symlink"):
        helper._write_policy_entries(link / "allowlist.toml", {})


def test_discovery_unit_shares_helper_runtime_group() -> None:
    helper_source = (Path(__file__).parents[1] / "scripts" / "smh-lxc-apt-helper.py").read_text(encoding="utf-8")
    unit = (Path(__file__).parents[1] / "scripts" / "smart-homelab-maintenance-lxc-discovery.service").read_text(encoding="utf-8")
    assert "User=root" in unit
    assert "Group=root" in unit
    assert "os.chown(socket_path, 0, agent_gid)" in helper_source
    assert "RuntimeDirectory=smart-homelab-maintenance" in unit
    assert "RuntimeDirectoryMode=0750" in unit
    assert "RuntimeDirectoryPreserve=yes" in unit


def test_helper_unit_preserves_shared_runtime_directory_on_restart() -> None:
    unit = (Path(__file__).parents[1] / "scripts" / "smart-homelab-maintenance-lxc-helper.service").read_text(encoding="utf-8")
    assert "RuntimeDirectory=smart-homelab-maintenance" in unit
    assert "RuntimeDirectoryPreserve=yes" in unit


def test_discovery_removes_its_socket_on_shutdown() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "smh-lxc-discovery.py").read_text(encoding="utf-8")
    assert "finally:" in source
    assert "current.st_ino == socket_inode" in source
    assert "path.unlink()" in source


def test_discovery_removes_only_a_verified_stale_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    socket_path = tmp_path / "discovery.sock"
    owner = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    owner.bind(str(socket_path))
    owner.close()
    monkeypatch.setattr(discovery, "_live_unix_socket_inodes", lambda: set())
    monkeypatch.setattr(discovery.Path, "lstat", lambda _path: SimpleNamespace(
        st_mode=stat.S_IFSOCK | 0o660, st_uid=0, st_gid=1234, st_ino=101
    ))

    discovery._remove_stale_socket(socket_path, 1234)

    assert not socket_path.exists()


def test_discovery_refuses_active_socket_and_preserves_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    socket_path = tmp_path / "discovery.sock"
    owner = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    owner.bind(str(socket_path))
    owner.listen(1)
    monkeypatch.setattr(discovery.Path, "lstat", lambda _path: SimpleNamespace(
        st_mode=stat.S_IFSOCK | 0o660, st_uid=0, st_gid=1234, st_ino=owner.fileno()
    ))
    monkeypatch.setattr(discovery, "_live_unix_socket_inodes", lambda: {owner.fileno()})
    try:
        with pytest.raises(RuntimeError, match="active"):
            discovery._remove_stale_socket(socket_path, 1234)
        assert socket_path.exists()
    finally:
        owner.close()


def test_discovery_refuses_symlink_and_unexpected_type(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("protected", encoding="utf-8")
    link = tmp_path / "discovery.sock"
    link.symlink_to(target)
    with pytest.raises(RuntimeError, match="not an owned Unix socket"):
        discovery._remove_stale_socket(link, os.getgid())
    assert target.read_text(encoding="utf-8") == "protected"

    regular = tmp_path / "regular.sock"
    regular.write_text("protected", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not an owned Unix socket"):
        discovery._remove_stale_socket(regular, os.getgid())


def test_discovery_start_uses_lock_and_inode_guard() -> None:
    source = DISCOVERY_PATH.read_text(encoding="utf-8")
    assert "_DiscoveryStartLock" in source
    assert "_live_unix_socket_inodes" in source
    assert "socket_inode = os.fstat(server.fileno()).st_ino" in source


def test_discovery_accepts_only_the_legacy_root_group_for_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    socket_path = tmp_path / "discovery.sock"
    owner = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    owner.bind(str(socket_path))
    owner.close()
    monkeypatch.setattr(discovery.Path, "lstat", lambda _path: SimpleNamespace(
        st_mode=stat.S_IFSOCK | 0o660, st_uid=0, st_gid=0, st_ino=102
    ))
    monkeypatch.setattr(discovery, "_live_unix_socket_inodes", lambda: set())
    discovery._remove_stale_socket(socket_path, 4321)
    assert not socket_path.exists()


def test_discovery_refuses_unexpected_socket_group(tmp_path: Path) -> None:
    socket_path = tmp_path / "discovery.sock"
    owner = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    owner.bind(str(socket_path))
    owner.close()
    metadata = SimpleNamespace(st_mode=stat.S_IFSOCK | 0o660, st_uid=0, st_gid=4321, st_ino=103)
    with pytest.raises(RuntimeError, match="ownership or mode"):
        discovery._validate_stale_socket_metadata(metadata, 9876, set())
    assert socket_path.exists()


def test_official_helper_installer_is_preflight_only_by_default_and_never_wildcards() -> None:
    installer = (Path(__file__).parents[1] / "scripts" / "install-lxc-helper.sh").read_text(encoding="utf-8")
    assert "--apply" in installer
    assert "--start" in installer
    assert 'if [[ "$apply" -ne 1 ]]' in installer
    assert "Empty by default" in installer
    assert "wildcards" in installer
    assert "systemctl daemon-reload" in installer


def test_discovery_only_installer_is_explicit_and_isolated() -> None:
    installer = (Path(__file__).parents[1] / "scripts" / "install-lxc-helper.sh").read_text(encoding="utf-8")
    assert "--discovery-only" in installer
    assert "--start-discovery" in installer
    assert "--confirm" in installer
    assert 'targets=("$DISCOVERY_PATH" "$DISCOVERY_UNIT")' in installer
    assert 'systemctl start "${AGENT_NAME}-lxc-discovery.service"' in installer
    assert 'systemctl start "${AGENT_NAME}-lxc-helper.service"' in installer
    assert "Discovery-only-Apply erfordert --confirm" in installer
    assert "Discovery-only-Preflight PASS" in installer


def test_installer_preserves_existing_allowlist_and_stages_rollback() -> None:
    installer = (Path(__file__).parents[1] / "scripts" / "install-lxc-helper.sh").read_text(encoding="utf-8")
    assert 'install -m 0600 -o root -g root "$HELPER_ETC" "$stage/allowlist"' in installer
    assert 'rollback="$ROLLBACK_ROOT/' in installer
    assert 'install -m 0600 -o root -g root "$1" "$rollback/$2"' in installer
