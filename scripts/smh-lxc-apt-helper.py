#!/usr/bin/env python3
"""Root-side, fixed-scope LXC APT inspection helper.

This file is not active merely because it is present in the repository. A
future installation must place it root-owned under the fixed helper path and
pair it with a root-owned allowlist and a root-owned Unix-socket service.
"""

from __future__ import annotations

import json
import os
import argparse
import socket
import socketserver
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Mapping

DEFAULT_ALLOWLIST = Path("/etc/smart-homelab-maintenance/lxc-apt-allowlist.toml")
MAX_OUTPUT_BYTES = 256_000
COMMAND_TIMEOUT_SECONDS = 10
ALLOWED_OPERATIONS = {"read", "simulate"}


class HelperError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _load_allowlist(path: Path = DEFAULT_ALLOWLIST) -> set[int]:
    try:
        stat = path.stat()
        if stat.st_uid != 0 or stat.st_mode & 0o022:
            raise HelperError("allowlist_permissions", "LXC allowlist must be root-owned and not writable by group/others")
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise HelperError("allowlist_unavailable", "root-owned LXC allowlist is unavailable") from exc
    entries = raw.get("containers", {})
    if not isinstance(entries, dict):
        raise HelperError("allowlist_invalid", "LXC allowlist must contain a containers table")
    allowed: set[int] = set()
    for raw_id, values in entries.items():
        if not isinstance(raw_id, str) or not raw_id.isdigit() or not isinstance(values, dict):
            raise HelperError("allowlist_invalid", "LXC allowlist contains an invalid entry")
        vmid = int(raw_id)
        if not 1 <= vmid <= 999_999:
            raise HelperError("allowlist_invalid", "LXC ID is outside the permitted range")
        if values.get("authorized") is not True or values.get("package_manager") != "apt":
            continue
        if str(values.get("os_name", "")).lower() not in {"debian", "ubuntu"}:
            continue
        if not isinstance(values.get("os_version"), str) or not values["os_version"]:
            continue
        allowed.add(vmid)
    return allowed


def validate_request(request: Any, allowed_ids: set[int]) -> tuple[int, str]:
    if not isinstance(request, dict) or set(request) != {"container_id", "operation"}:
        raise HelperError("invalid_request", "request must contain only container_id and operation")
    vmid = request["container_id"]
    operation = request["operation"]
    if not isinstance(vmid, int) or isinstance(vmid, bool) or not 1 <= vmid <= 999_999:
        raise HelperError("invalid_container", "container_id must be a numeric Proxmox ID")
    if operation not in ALLOWED_OPERATIONS:
        raise HelperError("operation_not_allowed", "only read and simulate are allowed")
    if vmid not in allowed_ids:
        raise HelperError("container_not_allowed", "container is not in the root-owned allowlist")
    return vmid, operation


def build_argv(vmid: int, operation: str) -> list[str]:
    if operation == "read":
        guest_command = ["/usr/bin/apt", "list", "--upgradable"]
    elif operation == "simulate":
        guest_command = ["/usr/bin/apt-get", "--simulate", "--no-remove", "-o", "Debug::NoLocking=true", "upgrade"]
    else:
        raise HelperError("operation_not_allowed", "only read and simulate are allowed")
    return ["/usr/sbin/pct", "exec", str(vmid), "--", *guest_command]


def _run(argv: list[str]) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired as exc:
        raise HelperError("timeout", "fixed guest operation timed out") from exc
    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    if len(stdout.encode()) + len(stderr.encode()) > MAX_OUTPUT_BYTES:
        raise HelperError("output_limit", "guest operation output exceeded the limit")
    return int(completed.returncode), stdout, stderr


def handle(request: Any, *, allowed_ids: set[int], run=_run) -> dict[str, Any]:
    try:
        vmid, operation = validate_request(request, allowed_ids)
        status_code, status_out, status_err = run(["/usr/sbin/pct", "status", str(vmid)])
        if status_code != 0:
            raise HelperError("status_failed", "container status could not be read")
        if status_out.strip() != "status: running":
            raise HelperError("not_running", "stopped containers are never started or probed")
        code, stdout, stderr = run(build_argv(vmid, operation))
        return {"ok": code == 0, "container_id": vmid, "operation": operation, "returncode": code, "stdout": stdout, "stderr": stderr}
    except HelperError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args(argv)
    if args.serve:
        serve("/run/smart-homelab-maintenance/lxc-apt-helper.sock")
        return 0
    try:
        request = json.load(sys.stdin)
        allowed = _load_allowlist()
        response = handle(request, allowed_ids=allowed)
    except (json.JSONDecodeError, OSError, HelperError) as exc:
        if isinstance(exc, HelperError):
            response = {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
        else:
            response = {"ok": False, "error": {"code": "invalid_request", "message": "request is not valid JSON"}}
    print(json.dumps(response, separators=(",", ":")))
    return 0 if response.get("ok") else 1


class _SocketHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline(16_385)
        if len(line) > 16_384 or not line.endswith(b"\n"):
            response = {"ok": False, "error": {"code": "request_limit", "message": "request exceeded the limit"}}
        else:
            try:
                request = json.loads(line.decode("utf-8"))
                response = handle(request, allowed_ids=self.server.allowed_ids)
            except (UnicodeDecodeError, json.JSONDecodeError):
                response = {"ok": False, "error": {"code": "invalid_request", "message": "request is not valid JSON"}}
        self.wfile.write((json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8"))


class _UnixHelperServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, socket_path: str, allowed_ids: set[int]) -> None:
        self.allowed_ids = allowed_ids
        super().__init__(socket_path, _SocketHandler)


def serve(socket_path: str, *, allowlist: Path = DEFAULT_ALLOWLIST) -> None:
    """Serve the fixed protocol from a root-owned systemd service."""
    if socket_path != "/run/smart-homelab-maintenance/lxc-apt-helper.sock":
        raise HelperError("socket_path_invalid", "helper socket path is fixed")
    allowed = _load_allowlist(allowlist)
    Path(socket_path).parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    try:
        with _UnixHelperServer(socket_path, allowed) as server:
            os.chmod(socket_path, 0o660)
            server.serve_forever()
    finally:
        try:
            os.unlink(socket_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
