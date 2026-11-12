from __future__ import annotations

import importlib.util
import json
import socket
import struct
from pathlib import Path


DISCOVERY_PATH = Path(__file__).parents[1] / "scripts" / "smh-lxc-discovery.py"
SPEC = importlib.util.spec_from_file_location("smh_lxc_discovery_peer_tests", DISCOVERY_PATH)
assert SPEC and SPEC.loader
discovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(discovery)


class FakePeerSocket:
    def __init__(self, pid: int, uid: int, gid: int) -> None:
        self.credentials = struct.pack("3i", pid, uid, gid)

    def getsockopt(self, *_args: object) -> bytes:
        return self.credentials


def set_expected_uid(monkeypatch, uid: int) -> None:
    monkeypatch.setattr(
        discovery.pwd,
        "getpwnam",
        lambda _name: type("PasswordEntry", (), {"pw_uid": uid})(),
    )
    monkeypatch.delenv("SMH_DISCOVERY_TEST_ALLOW_PEER_UID_MISMATCH", raising=False)
    monkeypatch.delenv("SMH_DISCOVERY_TEST_CLIENT_UID", raising=False)


def test_peer_credentials_use_uid_field_not_pid_or_gid(monkeypatch) -> None:
    set_expected_uid(monkeypatch, 997)

    assert discovery._peer_allowed(FakePeerSocket(pid=123456, uid=997, gid=989)) is True
    assert discovery._peer_allowed(FakePeerSocket(pid=997, uid=424242, gid=989)) is False
    assert discovery._peer_allowed(FakePeerSocket(pid=123456, uid=424242, gid=997)) is False


def test_handler_keeps_internal_errors_out_of_generic_response(monkeypatch) -> None:
    monkeypatch.setattr(discovery, "_peer_allowed", lambda _sock: True)

    def fail_probe(_container_id: int) -> dict[str, str]:
        raise RuntimeError("private detail")

    monkeypatch.setattr(discovery, "fixed_probe", fail_probe)

    server_socket, client_socket = socket.socketpair()
    try:
        client_socket.sendall(b'{"container_id":107,"operation":"probe"}\n')
        discovery._Handler(server_socket, None, None)
        response = json.loads(client_socket.recv(4096).decode("utf-8"))
    finally:
        server_socket.close()
        client_socket.close()

    assert response == {"ok": False, "error": {"code": "probe_failed"}}
    assert "private detail" not in json.dumps(response)
