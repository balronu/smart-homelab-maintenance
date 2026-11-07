from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from agent.smart_homelab_maintenance.updates import LXC_HELPER_SOCKET, RootHelperTransport
from agent.smart_homelab_maintenance.server import load_runtime_config


HELPER_PATH = Path(__file__).parents[1] / "scripts" / "smh-lxc-apt-helper.py"
SPEC = importlib.util.spec_from_file_location("smh_lxc_apt_helper", HELPER_PATH)
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def test_helper_builds_only_fixed_read_and_simulation_commands() -> None:
    read = helper.build_argv(101, "read")
    simulate = helper.build_argv(101, "simulate")
    assert read == ["/usr/sbin/pct", "exec", "101", "--", "/usr/bin/apt", "list", "--upgradable"]
    assert simulate == [
        "/usr/sbin/pct", "exec", "101", "--", "/usr/bin/apt-get", "--simulate",
        "--no-remove", "-o", "Debug::NoLocking=true", "upgrade",
    ]
    assert all("install" not in item and item != "update" for item in read + simulate)


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
    assert "_load_allowlist(self.server.allowlist_path)" in source
    assert "self.server.allowed_ids" not in source


def test_peer_credentials_reject_wrong_uid(monkeypatch) -> None:
    class FakeSocket:
        def getsockopt(self, *_args):
            import struct
            return struct.pack("3i", 424242, 1, 1)

    monkeypatch.setattr(helper.pwd, "getpwnam", lambda _name: type("Pw", (), {"pw_uid": 1234})())
    with pytest.raises(helper.HelperError, match="not authorized"):
        helper._require_agent_peer(FakeSocket())


def test_peer_credentials_accept_exact_uid(monkeypatch) -> None:
    class FakeSocket:
        def getsockopt(self, *_args):
            import struct
            return struct.pack("3i", 1234, 1, 1)

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
    assert "NoNewPrivileges=true" in unit
    assert "ExecStart=/usr/libexec/smart-homelab-maintenance/lxc-apt-helper --serve" in unit
    assert "ExecStart=/usr/sbin/pct" not in unit
    assert "NOPASSWD" not in unit
