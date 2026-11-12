#!/usr/bin/env python3
"""Root-owned fixed LXC OS/APT discovery service.

This service has no caller-supplied command path or arguments. It is installed
only by the official installer and remains inactive until its unit is
explicitly started.
"""

from __future__ import annotations

import os
import json
import fcntl
import pwd
import grp
import socket
import socketserver
import stat
import struct
import subprocess
import threading
from pathlib import Path
from typing import Any

DISCOVERY_SOCKET = "/run/smart-homelab-maintenance/lxc-discovery.sock"
DISCOVERY_START_LOCK = "/run/smart-homelab-maintenance/lxc-discovery.sock.lock"
EXPECTED_CLIENT_USER = "smart-homelab-maintenance"
MAX_REQUEST_BYTES = 16 * 1024

TIMEOUT = 10
MAX_OUTPUT = 64 * 1024
PROBE_LOCK = threading.Lock()


def _live_unix_socket_inodes(proc_net_unix: Path = Path("/proc/net/unix")) -> set[int]:
    """Return socket inodes still owned by the kernel."""

    inodes: set[int] = set()
    try:
        lines = proc_net_unix.read_text(encoding="ascii").splitlines()[1:]
    except (FileNotFoundError, PermissionError, OSError, UnicodeDecodeError) as exc:
        raise RuntimeError("cannot inspect kernel Unix socket table") from exc
    for line in lines:
        fields = line.split()
        if len(fields) >= 7 and fields[6].isdigit():
            inodes.add(int(fields[6]))
    return inodes


def _remove_stale_socket(path: Path, agent_gid: int) -> None:
    """Remove only a provably stale socket owned by this service."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    live_inodes = _live_unix_socket_inodes()
    _validate_stale_socket_metadata(metadata, agent_gid, live_inodes)
    path.unlink()


def _validate_stale_socket_metadata(metadata: os.stat_result, agent_gid: int, live_inodes: set[int]) -> None:
    """Fail closed unless metadata identifies an eligible detached socket."""

    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISSOCK(metadata.st_mode):
        raise RuntimeError("discovery socket path is not an owned Unix socket")
    # root:root is accepted only for the one-way migration from the old
    # RuntimeDirectoryPreserve=no layout. New sockets are always changed to
    # the agent group below before serving requests.
    if metadata.st_uid != 0 or metadata.st_gid not in {0, agent_gid} or stat.S_IMODE(metadata.st_mode) != 0o660:
        raise RuntimeError("discovery socket ownership or mode is unsafe")
    if metadata.st_ino in live_inodes:
        raise RuntimeError("discovery socket is active")


class _DiscoveryStartLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.fd: int | None = None

    def __enter__(self) -> "_DiscoveryStartLock":
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.chmod(self.path, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        assert self.fd is not None
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)
        self.fd = None


def _run(container_id: int, command: tuple[str, ...]) -> tuple[int, str]:
    completed = subprocess.run(
        ["/usr/sbin/pct", "exec", str(container_id), "--", *command],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=TIMEOUT,
        check=False,
    )
    output = (completed.stdout + completed.stderr)[: MAX_OUTPUT + 1]
    if len(output) > MAX_OUTPUT:
        raise ValueError("discovery output exceeds limit")
    return completed.returncode, output.decode("utf-8", "replace")


def fixed_probe(container_id: int) -> dict[str, str]:
    if not isinstance(container_id, int) or isinstance(container_id, bool) or not 1 <= container_id <= 999_999:
        raise ValueError("invalid container id")
    status, text = _run(container_id, ("/usr/bin/test", "-r", "/etc/os-release"))
    if status != 0:
        raise RuntimeError("container is not ready")
    results: dict[str, str] = {}
    commands = {
        "os_release": ("/usr/bin/cat", "/etc/os-release"),
        "apt_version": ("/usr/bin/apt-get", "--version"),
        "dpkg_version": ("/usr/bin/dpkg-query", "--version"),
    }
    for key, command in commands.items():
        status, output = _run(container_id, command)
        if status != 0:
            raise RuntimeError("fixed discovery command failed")
        results[key] = output
    for key, command in (("apt_exists", ("/usr/bin/test", "-x", "/usr/bin/apt-get")), ("dpkg_exists", ("/usr/bin/test", "-x", "/usr/bin/dpkg-query"))):
        status, _ = _run(container_id, command)
        results[key] = "yes" if status == 0 else "no"
    return results


def _peer_allowed(sock: socket.socket) -> bool:
    try:
        uid, _, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        expected_uid = pwd.getpwnam(EXPECTED_CLIENT_USER).pw_uid
        if os.environ.get("SMH_DISCOVERY_TEST_DIAGNOSTICS") == "1":
            if os.environ.get("SMH_DISCOVERY_TEST_ALLOW_PEER_UID_MISMATCH") == "1":
                return True
            override = os.environ.get("SMH_DISCOVERY_TEST_CLIENT_UID")
            if override is not None:
                expected_uid = int(override)
        return uid == expected_uid
    except (OSError, KeyError, struct.error):
        return False


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(TIMEOUT)
        result: dict[str, Any]
        try:
            if not _peer_allowed(self.request):
                detail = "unauthorized client"
                if os.environ.get("SMH_DISCOVERY_TEST_DIAGNOSTICS") == "1":
                    try:
                        peer_uid = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[0]
                        expected_uid = pwd.getpwnam(EXPECTED_CLIENT_USER).pw_uid
                        override = os.environ.get("SMH_DISCOVERY_TEST_CLIENT_UID")
                        if override is not None:
                            expected_uid = int(override)
                        detail = f"unauthorized client uid={peer_uid} expected={expected_uid}"
                    except (OSError, KeyError, struct.error):
                        pass
                raise ValueError(detail)
            line = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if len(line) > MAX_REQUEST_BYTES or not line.endswith(b"\n"):
                raise ValueError("request limit")
            request = json.loads(line.decode("utf-8"))
            if not isinstance(request, dict) or set(request) != {"container_id", "operation"}:
                raise ValueError("invalid request")
            container_id = request["container_id"]
            if request["operation"] != "probe" or not isinstance(container_id, int) or isinstance(container_id, bool) or not 1 <= container_id <= 999_999:
                raise ValueError("operation or container id not allowed")
            with PROBE_LOCK:
                result = {"ok": True, "container_id": container_id, "operation": "probe", "result": fixed_probe(container_id)}
        except (OSError, ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError, subprocess.TimeoutExpired) as exc:
            error: dict[str, str] = {"code": "probe_failed"}
            if os.environ.get("SMH_DISCOVERY_TEST_DIAGNOSTICS") == "1":
                error["detail"] = f"{type(exc).__name__}: {exc}"
            result = {"ok": False, "error": error}
        self.wfile.write((json.dumps(result, separators=(",", ":")) + "\n").encode("utf-8"))


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("root required")
    path = Path(DISCOVERY_SOCKET)
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    agent_gid = grp.getgrnam(EXPECTED_CLIENT_USER).gr_gid
    os.chown(path.parent, 0, agent_gid)
    os.chmod(path.parent, 0o750)
    with _DiscoveryStartLock(Path(DISCOVERY_START_LOCK)):
        try:
            _remove_stale_socket(path, agent_gid)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        server = socketserver.ThreadingUnixStreamServer(DISCOVERY_SOCKET, _Handler)
        socket_inode = os.fstat(server.fileno()).st_ino
    try:
        with server:
            server.daemon_threads = False
            os.chown(DISCOVERY_SOCKET, 0, agent_gid)
            os.chmod(DISCOVERY_SOCKET, 0o660)
            server.serve_forever()
    finally:
        try:
            current = path.lstat()
            if current.st_ino == socket_inode and stat.S_ISSOCK(current.st_mode):
                path.unlink()
        except FileNotFoundError:
            pass
