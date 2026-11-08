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
import selectors
import subprocess
import sys
import time
import tomllib
import pwd
import struct
import threading
from pathlib import Path
from typing import Any, Mapping

DEFAULT_ALLOWLIST = Path("/etc/smart-homelab-maintenance/lxc-apt-allowlist.toml")
MAX_OUTPUT_BYTES = 256_000
COMMAND_TIMEOUT_SECONDS = 10
ALLOWED_OPERATIONS = {"read", "simulate", "update"}
EXPECTED_CLIENT_USER = "smart-homelab-maintenance"
REQUEST_TIMEOUT_SECONDS = 10
MAX_REQUEST_BYTES = 16_384


class HelperError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _require_agent_peer(sock: socket.socket) -> None:
    try:
        _, uid, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        expected_uid = pwd.getpwnam(EXPECTED_CLIENT_USER).pw_uid
    except (OSError, KeyError, struct.error) as exc:
        raise HelperError("unauthorized_client", "client credentials could not be verified") from exc
    if uid != expected_uid:
        raise HelperError("unauthorized_client", "client is not authorized")


def _load_permissions(path: Path = DEFAULT_ALLOWLIST) -> tuple[set[int], set[int]]:
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
    simulation_allowed: set[int] = set()
    update_allowed: set[int] = set()
    for raw_id, values in entries.items():
        if not isinstance(raw_id, str) or not raw_id.isdigit() or not isinstance(values, dict):
            raise HelperError("allowlist_invalid", "LXC allowlist contains an invalid entry")
        vmid = int(raw_id)
        if not 1 <= vmid <= 999_999:
            raise HelperError("allowlist_invalid", "LXC ID is outside the permitted range")
        if values.get("package_manager") != "apt":
            continue
        if str(values.get("os_name", "")).lower() not in {"debian", "ubuntu"}:
            continue
        if not isinstance(values.get("os_version"), str) or not values["os_version"]:
            continue
        if values.get("authorized") is True or values.get("simulation_authorized") is True:
            simulation_allowed.add(vmid)
        if values.get("update_authorized") is True:
            update_allowed.add(vmid)
    return simulation_allowed, update_allowed


def _load_allowlist(path: Path = DEFAULT_ALLOWLIST) -> set[int]:
    """Compatibility view: return only simulation-authorized IDs."""
    return _load_permissions(path)[0]


def validate_request(request: Any, allowed_ids: set[int], update_ids: set[int] | None = None) -> tuple[int, str]:
    if not isinstance(request, dict) or set(request) != {"container_id", "operation"}:
        raise HelperError("invalid_request", "request must contain only container_id and operation")
    vmid = request["container_id"]
    operation = request["operation"]
    if not isinstance(vmid, int) or isinstance(vmid, bool) or not 1 <= vmid <= 999_999:
        raise HelperError("invalid_container", "container_id must be a numeric Proxmox ID")
    if operation not in ALLOWED_OPERATIONS:
        raise HelperError("operation_not_allowed", "operation is not allowed")
    if operation == "update":
        if vmid not in (update_ids or set()):
            raise HelperError("update_not_authorized", "container is not authorized for real updates")
    elif vmid not in allowed_ids:
        raise HelperError("container_not_allowed", "container is not in the root-owned allowlist")
    return vmid, operation


def build_argv(vmid: int, operation: str) -> list[str]:
    if operation == "read":
        guest_command = ["/usr/bin/apt", "list", "--upgradable"]
    elif operation == "simulate":
        guest_command = ["/usr/bin/apt-get", "--simulate", "--no-remove", "-o", "Debug::NoLocking=true", "upgrade"]
    elif operation == "update":
        guest_command = ["/usr/bin/apt-get", "update"]
    else:
        raise HelperError("operation_not_allowed", "operation is not allowed")
    return ["/usr/sbin/pct", "exec", str(vmid), "--", *guest_command]


def _run(argv: list[str]) -> tuple[int, str, str]:
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        assert process.stdout is not None and process.stderr is not None
        selector = selectors.DefaultSelector()
        try:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            output = {"stdout": bytearray(), "stderr": bytearray()}
            deadline = time.monotonic() + COMMAND_TIMEOUT_SECONDS
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, COMMAND_TIMEOUT_SECONDS)
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fileobj.fileno(), 16_384)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    output[key.data].extend(chunk)
                    if len(output["stdout"]) + len(output["stderr"]) > MAX_OUTPUT_BYTES:
                        raise HelperError("output_limit", "guest operation output exceeded the limit")
            returncode = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        finally:
            selector.close()
    except subprocess.TimeoutExpired as exc:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        raise HelperError("timeout", "fixed guest operation timed out") from exc
    except BaseException:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        raise
    finally:
        if process is not None:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
    return int(returncode), bytes(output["stdout"]).decode("utf-8", "replace"), bytes(output["stderr"]).decode("utf-8", "replace")


_UPDATE_LOCK = threading.Lock()


def handle(request: Any, *, allowed_ids: set[int], update_ids: set[int] | None = None, run=_run) -> dict[str, Any]:
    try:
        vmid, operation = validate_request(request, allowed_ids, update_ids)
        lock = _UPDATE_LOCK if operation == "update" else threading.Lock()
        with lock:
            status_code, status_out, status_err = run(["/usr/sbin/pct", "status", str(vmid)])
            if status_code != 0:
                raise HelperError("status_failed", "container status could not be read")
            if status_out.strip() != "status: running":
                raise HelperError("not_running", "stopped containers are never started or probed")
            steps = []
            code, stdout, stderr = run(build_argv(vmid, operation))
            steps.append({"name": "apt-update" if operation == "update" else operation, "returncode": code})
            if operation == "update" and code == 0:
                upgrade = ["/usr/sbin/pct", "exec", str(vmid), "--", "/usr/bin/apt-get", "--yes", "--no-remove", "upgrade"]
                upgrade_code, upgrade_stdout, upgrade_stderr = run(upgrade)
                steps.append({"name": "apt-upgrade", "returncode": upgrade_code})
                code = upgrade_code
                stdout = stdout + upgrade_stdout
                stderr = stderr + upgrade_stderr
        return {"ok": code == 0, "container_id": vmid, "operation": operation, "returncode": code, "stdout": stdout, "stderr": stderr, "steps": steps}
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
        allowed, update_allowed = _load_permissions()
        response = handle(request, allowed_ids=allowed, update_ids=update_allowed)
    except (json.JSONDecodeError, OSError, HelperError) as exc:
        if isinstance(exc, HelperError):
            response = {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
        else:
            response = {"ok": False, "error": {"code": "invalid_request", "message": "request is not valid JSON"}}
    print(json.dumps(response, separators=(",", ":")))
    return 0 if response.get("ok") else 1


class _SocketHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(REQUEST_TIMEOUT_SECONDS)
        try:
            _require_agent_peer(self.request)
        except HelperError as exc:
            response = {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
        else:
            try:
                line = self.rfile.readline(MAX_REQUEST_BYTES + 1)
                if len(line) > MAX_REQUEST_BYTES or not line.endswith(b"\n"):
                    raise HelperError("request_limit", "request exceeded the limit")
                request = json.loads(line.decode("utf-8"))
                allowed, update_allowed = _load_permissions(self.server.allowlist_path)
                response = handle(request, allowed_ids=allowed, update_ids=update_allowed)
            except socket.timeout:
                response = {"ok": False, "error": {"code": "timeout", "message": "helper request timed out"}}
            except HelperError as exc:
                response = {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
            except (UnicodeDecodeError, json.JSONDecodeError):
                response = {"ok": False, "error": {"code": "invalid_request", "message": "request is not valid JSON"}}
            except OSError:
                response = {"ok": False, "error": {"code": "allowlist_unavailable", "message": "root-owned LXC allowlist is unavailable"}}
        try:
            self.wfile.write((json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8"))
        except OSError:
            return


class _UnixHelperServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, socket_path: str, allowlist_path: Path) -> None:
        self.allowlist_path = allowlist_path
        super().__init__(socket_path, _SocketHandler)


def serve(socket_path: str, *, allowlist: Path = DEFAULT_ALLOWLIST) -> None:
    """Serve the fixed protocol from a root-owned systemd service."""
    if socket_path != "/run/smart-homelab-maintenance/lxc-apt-helper.sock":
        raise HelperError("socket_path_invalid", "helper socket path is fixed")
    _load_allowlist(allowlist)
    Path(socket_path).parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    try:
        with _UnixHelperServer(socket_path, allowlist) as server:
            os.chmod(socket_path, 0o660)
            server.serve_forever()
    finally:
        try:
            os.unlink(socket_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
