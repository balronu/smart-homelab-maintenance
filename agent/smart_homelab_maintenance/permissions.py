"""Root-owned, atomic per-container update permissions.

The agent is the only writer.  The helper remains the final enforcement
point, so a policy write can never grant access to an unsupported target by
itself.
"""

from __future__ import annotations

import os
import re
import json
import socket
import stat
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Mapping

from .errors import ValidationError

_TARGET = re.compile(r"^container:[1-9][0-9]{0,5}$")
_POLICY_SOCKET = "/run/smart-homelab-maintenance/lxc-apt-helper.sock"


class PolicyHelperTransport:
    """Use the root-owned helper for policy I/O without weakening file ACLs."""

    def __init__(self, *, timeout_seconds: float = 5.0, exchange=None) -> None:
        if not 1.0 <= timeout_seconds <= 15.0:
            raise ValueError("policy helper timeout must be between 1 and 15 seconds")
        self.timeout_seconds = timeout_seconds
        self._exchange = exchange

    def _call(self, request: dict[str, Any]) -> dict[str, Any]:
        payload = (json.dumps(request, separators=(",", ":")) + "\n").encode()
        try:
            if self._exchange is not None:
                raw = self._exchange(payload)
            else:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
                    channel.settimeout(self.timeout_seconds)
                    channel.connect(_POLICY_SOCKET)
                    channel.sendall(payload)
                    chunks: list[bytes] = []
                    total = 0
                    while True:
                        chunk = channel.recv(16_384)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        total += len(chunk)
                        if total > 256_000:
                            raise OSError("policy helper response exceeded the limit")
                        if b"\n" in chunk:
                            break
                    raw = b"".join(chunks)
            response = json.loads(raw.decode().splitlines()[0])
        except (OSError, ValueError, json.JSONDecodeError, IndexError) as exc:
            raise ValidationError("privileged policy helper is unavailable") from exc
        if not isinstance(response, dict) or response.get("ok") is not True:
            error = response.get("error", {}) if isinstance(response, dict) else {}
            raise ValidationError(str(error.get("message", "privileged policy operation failed")))
        return response

    def read(self) -> dict[str, dict[str, Any]]:
        response = self._call({"operation": "policy_read"})
        entries = response.get("entries")
        if not isinstance(entries, dict):
            raise ValidationError("privileged policy response is invalid")
        result: dict[str, dict[str, Any]] = {}
        for key, value in entries.items():
            if not isinstance(key, str) or not key.isdigit() or not isinstance(value, dict):
                raise ValidationError("privileged policy response is invalid")
            result[key] = dict(value)
        return result

    def set_permissions(self, target: str, *, simulation_authorized: bool, update_authorized: bool, metadata: Mapping[str, Any]) -> dict[str, Any]:
        return self._call({
            "operation": "policy_set",
            "target": target,
            "simulation_authorized": bool(simulation_authorized),
            "update_authorized": bool(update_authorized),
            "metadata": {key: str(metadata[key]) for key in ("os_name", "os_version", "package_manager") if metadata.get(key) is not None},
            "confirm": True,
        }).get("data", {})


class PermissionStore:
    def __init__(self, path: str | os.PathLike[str], *, require_root: bool = False, privileged_transport: PolicyHelperTransport | None = None) -> None:
        self.path = Path(path)
        if not self.path.is_absolute():
            raise ValueError("permission store path must be absolute")
        self.require_root = require_root
        self.privileged_transport = privileged_transport

    def _check_file(self) -> None:
        if self.path.is_symlink():
            raise ValidationError("permission store must not be a symlink")
        if not self.path.exists():
            return
        info = self.path.stat()
        if info.st_uid != 0 and self.require_root:
            raise ValidationError("permission store is not root-owned")
        if info.st_mode & 0o777 != 0o600:
            raise ValidationError("permission store is writable or has an unsafe mode")

    def read(self) -> dict[str, dict[str, Any]]:
        self._check_file()
        if self.privileged_transport is not None:
            return self.privileged_transport.read()
        if not self.path.exists():
            return {}
        try:
            with self.path.open("rb") as handle:
                raw = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ValidationError("permission store is invalid") from exc
        entries = raw.get("containers", {})
        if not isinstance(entries, dict):
            raise ValidationError("permission store containers table is invalid")
        result: dict[str, dict[str, Any]] = {}
        for raw_id, values in entries.items():
            if not isinstance(raw_id, str) or not raw_id.isdigit() or not isinstance(values, dict):
                raise ValidationError("permission store contains an invalid container")
            if not 1 <= int(raw_id) <= 999999:
                raise ValidationError("container id is invalid")
            result[raw_id] = dict(values)
        return result

    @staticmethod
    def _toml_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        raise ValidationError("permission metadata contains an unsupported value")

    def _render(self, entries: Mapping[str, Mapping[str, Any]]) -> str:
        lines = ["# Managed by Smart Homelab Maintenance; empty means no guest access.", ""]
        for raw_id in sorted(entries, key=int):
            lines.append(f'[containers."{raw_id}"]')
            for key in sorted(entries[raw_id]):
                value = entries[raw_id][key]
                if key not in {"authorized", "simulation_authorized", "update_authorized", "os_name", "os_version", "package_manager"}:
                    raise ValidationError("permission store contains an unsupported field")
                lines.append(f"{key} = {self._toml_value(value)}")
            lines.append("")
        return "\n".join(lines)

    def set_permissions(self, target: str, *, simulation_authorized: bool, update_authorized: bool, metadata: Mapping[str, Any]) -> dict[str, Any]:
        if not _TARGET.fullmatch(target):
            raise ValidationError("only numeric LXC targets may be authorized")
        self._check_file()
        if self.privileged_transport is not None:
            return self.privileged_transport.set_permissions(target, simulation_authorized=simulation_authorized, update_authorized=update_authorized, metadata=metadata)
        entries = self.read()
        raw_id = target.split(":", 1)[1]
        entry = dict(entries.get(raw_id, {}))
        entry.update({"simulation_authorized": bool(simulation_authorized), "update_authorized": bool(update_authorized)})
        for key in ("os_name", "os_version", "package_manager"):
            if metadata.get(key) is not None:
                entry[key] = str(metadata[key])
        entries[raw_id] = entry
        self.path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if self.path.parent.is_symlink():
            raise ValidationError("permission store directory must not be a symlink")
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent), text=True)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(self._render(entries))
                handle.flush()
                os.fsync(handle.fileno())
            if self.require_root and os.geteuid() != 0:
                raise ValidationError("root privileges are required to update the permission store")
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        return {"target": target, "simulation_authorized": bool(simulation_authorized), "update_authorized": bool(update_authorized)}
