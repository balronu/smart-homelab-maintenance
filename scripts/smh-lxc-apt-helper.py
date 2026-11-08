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
import re
import socket
import socketserver
import selectors
import subprocess
import sys
import time
import tomllib
import pwd
import grp
import struct
import threading
import tempfile
from pathlib import Path
from typing import Any, Mapping

DEFAULT_ALLOWLIST = Path("/etc/smart-homelab-maintenance/lxc-apt-allowlist.toml")
MAX_OUTPUT_BYTES = 256_000
COMMAND_TIMEOUT_SECONDS = 10
ALLOWED_OPERATIONS = {"read", "simulate", "update"}
PROBE_OPERATION = "probe"
POLICY_OPERATIONS = {"policy_read", "policy_set"}
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
        if stat.st_uid != 0 or stat.st_mode & 0o777 != 0o600:
            raise HelperError("allowlist_permissions", "LXC allowlist must be root-owned with mode 0600")
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


def _load_policy_entries(path: Path = DEFAULT_ALLOWLIST) -> dict[str, dict[str, Any]]:
    try:
        stat = path.stat()
        if stat.st_uid != 0 or stat.st_mode & 0o777 != 0o600:
            raise HelperError("allowlist_permissions", "LXC allowlist must be root-owned with mode 0600")
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise HelperError("allowlist_unavailable", "root-owned LXC allowlist is unavailable") from exc
    entries = raw.get("containers", {})
    if not isinstance(entries, dict):
        raise HelperError("allowlist_invalid", "LXC allowlist must contain a containers table")
    result: dict[str, dict[str, Any]] = {}
    for raw_id, values in entries.items():
        if not isinstance(raw_id, str) or not raw_id.isdigit() or not isinstance(values, dict) or not 1 <= int(raw_id) <= 999999:
            raise HelperError("allowlist_invalid", "LXC allowlist contains an invalid entry")
        allowed = {"authorized", "simulation_authorized", "update_authorized", "os_name", "os_version", "package_manager"}
        if set(values) - allowed:
            raise HelperError("allowlist_invalid", "LXC allowlist contains an unsupported field")
        result[raw_id] = dict(values)
    return result


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise HelperError("allowlist_invalid", "LXC allowlist contains an unsupported value")


def _validate_policy_directory(path: Path) -> None:
    directory = path.parent
    try:
        info = directory.stat()
    except OSError as exc:
        raise HelperError("allowlist_unavailable", "root-owned LXC allowlist directory is unavailable") from exc
    if not directory.is_dir() or directory.is_symlink() or info.st_uid != 0 or info.st_mode & 0o077:
        raise HelperError("allowlist_permissions", "LXC allowlist directory must be root-owned and private")


def _validate_policy_entries(entries: dict[str, dict[str, Any]]) -> None:
    allowed = {"authorized", "simulation_authorized", "update_authorized", "os_name", "os_version", "package_manager"}
    for raw_id, values in entries.items():
        if not isinstance(raw_id, str) or not re.fullmatch(r"[1-9][0-9]{0,5}", raw_id) or not isinstance(values, dict):
            raise HelperError("allowlist_invalid", "LXC allowlist contains an invalid entry")
        if set(values) - allowed:
            raise HelperError("allowlist_invalid", "LXC allowlist contains an unsupported field")
        for key, value in values.items():
            if key in {"authorized", "simulation_authorized", "update_authorized"} and not isinstance(value, bool):
                raise HelperError("allowlist_invalid", "LXC allowlist authorization fields must be boolean")
            if key in {"os_name", "os_version", "package_manager"} and not isinstance(value, str):
                raise HelperError("allowlist_invalid", "LXC allowlist metadata fields must be strings")


def _write_policy_entries(path: Path, entries: dict[str, dict[str, Any]]) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise HelperError("allowlist_permissions", "LXC allowlist path must not be a symlink")
    _validate_policy_directory(path)
    _validate_policy_entries(entries)
    fd = -1
    temporary = ""
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
        if os.fstat(fd).st_dev != os.stat(path.parent, follow_symlinks=False).st_dev:
            raise HelperError("allowlist_unavailable", "temporary policy file is not on the policy filesystem")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            handle.write("# Managed by Smart Homelab Maintenance; empty means no guest access.\n\n")
            for raw_id in sorted(entries, key=int):
                handle.write(f'[containers."{raw_id}"]\n')
                for key in sorted(entries[raw_id]):
                    handle.write(f"{key} = {_toml_value(entries[raw_id][key])}\n")
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if os.geteuid() == 0:
            os.chown(path, 0, 0)
        os.chmod(path, 0o600)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            if temporary:
                os.unlink(temporary)
        except FileNotFoundError:
            pass


def handle_policy(request: Any, path: Path = DEFAULT_ALLOWLIST) -> dict[str, Any]:
    if not isinstance(request, dict) or not isinstance(request.get("operation"), str):
        raise HelperError("invalid_request", "policy request is invalid")
    operation = request["operation"]
    if operation == "policy_read":
        if set(request) != {"operation"}:
            raise HelperError("invalid_request", "policy_read accepts no additional fields")
        return {"ok": True, "operation": operation, "entries": _load_policy_entries(path)}
    if operation != "policy_set" or set(request) != {"operation", "target", "simulation_authorized", "update_authorized", "metadata", "confirm"}:
        raise HelperError("invalid_request", "policy_set request is invalid")
    target = request["target"]
    if not isinstance(target, str) or not re.fullmatch(r"container:[1-9][0-9]{0,5}", target):
        raise HelperError("invalid_container", "only numeric LXC targets may be authorized")
    if request["confirm"] is not True or not isinstance(request["simulation_authorized"], bool) or not isinstance(request["update_authorized"], bool):
        raise HelperError("confirmation_required", "policy changes require explicit confirmation and boolean permissions")
    if request["update_authorized"] and not request["simulation_authorized"]:
        raise HelperError("invalid_permissions", "update authorization requires simulation authorization")
    metadata = request["metadata"]
    if not isinstance(metadata, dict) or set(metadata) - {"os_name", "os_version", "package_manager"} or any(not isinstance(v, str) for v in metadata.values()):
        raise HelperError("invalid_metadata", "policy metadata is invalid")
    entries = _load_policy_entries(path)
    raw_id = target.split(":", 1)[1]
    entry = dict(entries.get(raw_id, {}))
    simulation = request["simulation_authorized"]
    entry.update({"authorized": simulation, "simulation_authorized": simulation, "update_authorized": request["update_authorized"]})
    entry.update(metadata)
    entries[raw_id] = entry
    _write_policy_entries(path, entries)
    return {"ok": True, "operation": operation, "data": {"target": target, "simulation_authorized": simulation, "update_authorized": request["update_authorized"]}}


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


def _parse_os_release(raw: str) -> tuple[str, str]:
    values: dict[str, str] = {}
    for line in raw.splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {"ID", "ID_LIKE", "VERSION_ID"}:
            values[key] = value.strip().strip('"').strip("'")
    ids = {item.strip().lower() for item in (values.get("ID", "") + " " + values.get("ID_LIKE", "")).split()}
    if not ids.intersection({"debian", "ubuntu"}) or not values.get("VERSION_ID"):
        raise HelperError("unsupported_os", "container is not a proven Debian/Ubuntu system")
    os_name = "Ubuntu" if "ubuntu" in ids else "Debian"
    return os_name, values["VERSION_ID"]


def probe_target(request: Any, *, run=None) -> dict[str, Any]:
    """Prove a running Debian/Ubuntu APT LXC using fixed read-only commands."""
    run = run or _run
    if not isinstance(request, dict) or set(request) != {"container_id", "operation"}:
        raise HelperError("invalid_request", "probe request must contain only container_id and operation")
    vmid = request["container_id"]
    if not isinstance(vmid, int) or isinstance(vmid, bool) or not 1 <= vmid <= 999_999:
        raise HelperError("invalid_container", "container_id must be a numeric Proxmox ID")
    status_code, status_out, _ = run(["/usr/sbin/pct", "status", str(vmid)])
    if status_code != 0:
        raise HelperError("status_failed", "container status could not be read")
    if status_out.strip() != "status: running":
        raise HelperError("not_running", "stopped containers are never started or probed")
    os_code, os_out, _ = run(["/usr/sbin/pct", "exec", str(vmid), "--", "/usr/bin/cat", "/etc/os-release"])
    if os_code != 0:
        raise HelperError("os_release_unavailable", "container operating system could not be proven")
    os_name, os_version = _parse_os_release(os_out)
    for executable in ("/usr/bin/apt-get", "/usr/bin/apt"):
        apt_code, _, _ = run(["/usr/sbin/pct", "exec", str(vmid), "--", "/usr/bin/test", "-x", executable])
        if apt_code != 0:
            raise HelperError("apt_unavailable", "container APT support could not be proven")
    return {"ok": True, "operation": PROBE_OPERATION, "container_id": vmid, "running": True,
            "supported": True, "os_name": os_name, "os_version": os_version, "package_manager": "apt"}


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
        if isinstance(request, dict) and request.get("operation") == PROBE_OPERATION:
            return probe_target(request, run=run)
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
                if isinstance(request, dict) and request.get("operation") in POLICY_OPERATIONS:
                    response = handle_policy(request, self.server.allowlist_path)
                elif isinstance(request, dict) and request.get("operation") == PROBE_OPERATION:
                    response = probe_target(request)
                else:
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
    runtime_dir = Path(socket_path).parent
    runtime_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
    agent_gid = grp.getgrnam(EXPECTED_CLIENT_USER).gr_gid
    os.chown(runtime_dir, 0, agent_gid)
    os.chmod(runtime_dir, 0o750)
    try:
        with _UnixHelperServer(socket_path, allowlist) as server:
            os.chown(socket_path, 0, agent_gid)
            os.chmod(socket_path, 0o660)
            server.serve_forever()
    finally:
        try:
            os.unlink(socket_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
