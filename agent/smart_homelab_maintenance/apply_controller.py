"""Explicit, serialized allowlist apply controller.

Planning remains separate from application. The default operation is a
read-only preview; a caller must pass an explicit apply flag. This module is
not wired to the production agent in this phase.
"""

from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .authorization import AllowlistPlan, render_allowlist


@dataclass(frozen=True, slots=True)
class ApplyResult:
    applied: bool
    changed: bool
    authorized_ids: tuple[int, ...]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"applied": self.applied, "changed": self.changed, "authorized_ids": list(self.authorized_ids), "error": self.error}


class AllowlistApplyController:
    def __init__(self, path: Path, *, require_root: bool = True) -> None:
        self.path = path
        self.require_root = require_root
        self._lock = threading.Lock()

    def preview(self, plan: AllowlistPlan) -> ApplyResult:
        return ApplyResult(False, self._content(plan) != self._existing(), tuple(sorted(plan.authorized_ids)))

    def apply(self, plan: AllowlistPlan, *, confirmed: bool = False) -> ApplyResult:
        if not confirmed:
            return self.preview(plan)
        if self.require_root and os.geteuid() != 0:
            return ApplyResult(False, False, tuple(sorted(plan.authorized_ids)), "root_required")
        content = self._content(plan)
        with self._lock:
            try:
                old = self._existing()
                if old == content:
                    return ApplyResult(True, False, tuple(sorted(plan.authorized_ids)))
                self.path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
                try:
                    os.fchmod(fd, 0o600)
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, self.path)
                    os.chmod(self.path, 0o600)
                except BaseException:
                    try:
                        os.unlink(temporary)
                    except FileNotFoundError:
                        pass
                    raise
                return ApplyResult(True, True, tuple(sorted(plan.authorized_ids)))
            except OSError as exc:
                return ApplyResult(False, False, tuple(sorted(plan.authorized_ids)), "allowlist_apply_failed")

    def _content(self, plan: AllowlistPlan) -> str:
        return render_allowlist(plan)

    def _existing(self) -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
