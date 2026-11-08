#!/usr/bin/env python3
"""Root-owned fixed LXC OS/APT discovery service.

This service has no caller-supplied command path or arguments. It is installed
only by the official installer and remains inactive until its unit is
explicitly started.
"""

from __future__ import annotations

import os
import json
import pwd
import socket
import socketserver
import struct
import subprocess
from pathlib import Path
from typing import Any

DISCOVERY_SOCKET = "/run/smart-homelab-maintenance/lxc-discovery.sock"
EXPECTED_CLIENT_USER = "smart-homelab-maintenance"
MAX_REQUEST_BYTES = 16 * 1024

TIMEOUT = 10
MAX_OUTPUT = 64 * 1024


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
        return uid == pwd.getpwnam(EXPECTED_CLIENT_USER).pw_uid
    except (OSError, KeyError, struct.error):
        return False


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(TIMEOUT)
        result: dict[str, Any]
        try:
            if not _peer_allowed(self.request):
                raise ValueError("unauthorized client")
            line = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if len(line) > MAX_REQUEST_BYTES or not line.endswith(b"\n"):
                raise ValueError("request limit")
            request = json.loads(line.decode("utf-8"))
            if not isinstance(request, dict) or set(request) != {"container_id", "operation"}:
                raise ValueError("invalid request")
            container_id = request["container_id"]
            if request["operation"] != "probe" or not isinstance(container_id, int) or isinstance(container_id, bool) or not 1 <= container_id <= 999_999:
                raise ValueError("operation or container id not allowed")
            result = {"ok": True, "container_id": container_id, "operation": "probe", "result": fixed_probe(container_id)}
        except (OSError, ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError, subprocess.TimeoutExpired):
            result = {"ok": False, "error": {"code": "probe_failed"}}
        self.wfile.write((json.dumps(result, separators=(",", ":")) + "\n").encode("utf-8"))


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("root required")
    path = Path(DISCOVERY_SOCKET)
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    if path.exists():
        raise SystemExit("discovery socket already exists")
    with socketserver.ThreadingUnixStreamServer(DISCOVERY_SOCKET, _Handler) as server:
        server.daemon_threads = False
        os.chmod(DISCOVERY_SOCKET, 0o660)
        server.serve_forever()
