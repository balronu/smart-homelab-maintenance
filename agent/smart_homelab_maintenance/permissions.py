"""Root-owned, atomic per-container update permissions.

The agent is the only writer.  The helper remains the final enforcement
point, so a policy write can never grant access to an unsupported target by
itself.
"""

from __future__ import annotations

import os
import re
import stat
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Mapping

from .errors import ValidationError

_TARGET = re.compile(r"^container:[1-9][0-9]{0,5}$")


class PermissionStore:
    def __init__(self, path: str | os.PathLike[str], *, require_root: bool = False) -> None:
        self.path = Path(path)
        if not self.path.is_absolute():
            raise ValueError("permission store path must be absolute")
        self.require_root = require_root

    def _check_file(self) -> None:
        if self.path.is_symlink():
            raise ValidationError("permission store must not be a symlink")
        if not self.path.exists():
            return
        info = self.path.stat()
        if info.st_uid != 0 and self.require_root:
            raise ValidationError("permission store is not root-owned")
        if info.st_mode & 0o022:
            raise ValidationError("permission store is writable by group or others")

    def read(self) -> dict[str, dict[str, Any]]:
        self._check_file()
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
