"""Allowlisted, read-only Linux package inspection and simulation.

This module deliberately has no generic command or target-path input.  The
only live command sequence is the fixed apt simulation, and the only guest
transport is the validated local ``pct exec <vmid>`` form.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from .errors import ValidationError
from .types import utc_now

_VMID = re.compile(r"^[1-9][0-9]{0,5}$")
_TARGET = re.compile(r"^(host|container:[1-9][0-9]{0,5})$")
_INST = re.compile(r"^Inst\s+(\S+)(?:\s+\[([^]]*)\])?\s+\(([^ )]+)")
_REMV = re.compile(r"^Remv\s+(\S+)")


@dataclass(frozen=True, slots=True)
class PackageChange:
    name: str
    operation: str
    installed_version: str | None = None
    available_version: str | None = None
    security: bool | None = None


@dataclass(frozen=True, slots=True)
class UpdateResult:
    target: str
    name: str
    reachable: bool
    supported: bool
    os_name: str
    os_version: str
    package_manager: str | None
    status: str
    available_count: int | None
    security_count: int | None
    packages: tuple[PackageChange, ...] = ()
    held_packages: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    removals: tuple[str, ...] = ()
    checked_at: str | None = None
    error: str | None = None
    stale_after_seconds: int = 21600
    plan_digest: str | None = None
    dry_run_supported: bool = False

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["packages"] = [asdict(item) for item in self.packages]
        result["held_packages"] = list(self.held_packages)
        result["conflicts"] = list(self.conflicts)
        result["removals"] = list(self.removals)
        result["fresh"] = bool(self.checked_at and self.status not in {"unknown", "error", "unsupported"})
        return result

    def is_fresh(self, now: float | None = None) -> bool:
        if not self.checked_at or self.status in {"unknown", "error", "unsupported"}:
            return False
        try:
            checked = datetime.fromisoformat(self.checked_at)
            age = (datetime.now(timezone.utc) - checked).total_seconds() if now is None else now - checked.timestamp()
            return age < self.stale_after_seconds
        except (TypeError, ValueError):
            return False


@dataclass(frozen=True, slots=True)
class DryRunResult:
    target: str
    simulation: bool
    success: bool
    safe: bool
    plan_digest: str | None
    packages: tuple[PackageChange, ...] = ()
    held_packages: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    removals: tuple[str, ...] = ()
    executed_at: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["packages"] = [asdict(item) for item in self.packages]
        result["held_packages"] = list(self.held_packages)
        result["conflicts"] = list(self.conflicts)
        result["removals"] = list(self.removals)
        return result


@dataclass(frozen=True, slots=True)
class ProbeTarget:
    target: str
    name: str
    vmid: int | None = None
    os_name: str = "unknown"
    os_version: str = "unknown"
    package_manager: str | None = None


class AptCommandRunner:
    """Run only a fixed apt simulation, never an install or index refresh."""

    def __init__(self, *, timeout_seconds: float = 8.0, run: Callable[..., Any] | None = None) -> None:
        if not 0.5 <= timeout_seconds <= 30:
            raise ValueError("apt timeout must be between 0.5 and 30 seconds")
        self.timeout_seconds = timeout_seconds
        self._run = run or subprocess.run

    @staticmethod
    def _argv(vmid: int | None) -> list[str]:
        apt = ["apt-get", "--simulate", "--no-remove", "-o", "Debug::NoLocking=true", "upgrade"]
        if vmid is None:
            return apt
        if not 1 <= vmid <= 999_999:
            raise ValidationError("container id is invalid")
        return ["pct", "exec", str(vmid), "--", *apt]

    def simulate(self, vmid: int | None = None) -> tuple[int, str, str]:
        argv = self._argv(vmid)
        if vmid is not None and shutil.which("pct") is None:
            raise FileNotFoundError("pct guest transport is unavailable")
        if vmid is None and shutil.which("apt-get") is None:
            raise FileNotFoundError("apt-get is unavailable")
        completed = self._run(argv, capture_output=True, text=True, timeout=self.timeout_seconds, check=False)
        return int(completed.returncode), str(completed.stdout or ""), str(completed.stderr or "")


def _parse_apt(stdout: str, stderr: str) -> tuple[tuple[PackageChange, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    packages: list[PackageChange] = []
    removals: list[str] = []
    held: list[str] = []
    conflicts: list[str] = []
    for line in (stdout + "\n" + stderr).splitlines():
        stripped = line.strip()
        match = _INST.match(stripped)
        if match:
            name, old, available = match.groups()
            packages.append(PackageChange(name, "upgrade" if old else "install", old, available, "security" in stripped.lower() or "-security" in available.lower()))
        removal = _REMV.match(stripped)
        if removal:
            removals.append(removal.group(1))
        if stripped.startswith("The following packages have been kept back:"):
            continue
        if held or stripped.startswith("The following packages will be kept back:"):
            held.extend(token.strip(",") for token in stripped.split() if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.:-]*", token) and token.lower() not in {"the", "following", "packages", "have", "been", "will", "kept", "back"})
        if any(word in stripped.lower() for word in ("conflict", "unmet dependencies", "held broken packages")):
            conflicts.append(stripped[:240])
    unique = {item.name: item for item in packages}
    return tuple(unique.values()), tuple(sorted(set(held))), tuple(sorted(set(conflicts))), tuple(sorted(set(removals)))


class UpdateService:
    """Passive cached checks and explicitly confirmed simulations."""

    def __init__(self, targets: Callable[[], Sequence[ProbeTarget]], *, runner: AptCommandRunner | None = None, clock: Callable[[], float] | None = None) -> None:
        self._targets = targets
        self._runner = runner or AptCommandRunner()
        self._clock = clock or time.monotonic
        self._cache: dict[str, tuple[UpdateResult, float]] = {}

    def target_map(self) -> dict[str, ProbeTarget]:
        return {target.target: target for target in self._targets()}

    def _check_uncached(self, target: ProbeTarget) -> UpdateResult:
        if target.package_manager != "apt" or target.os_name.lower() not in {"debian", "ubuntu"}:
            return UpdateResult(target.target, target.name, False, False, target.os_name, target.os_version, target.package_manager, "unsupported", None, None, error="supported Debian/Ubuntu apt target not proven")
        try:
            code, stdout, stderr = self._runner.simulate(target.vmid)
        except (FileNotFoundError, PermissionError) as exc:
            return UpdateResult(target.target, target.name, False, True, target.os_name, target.os_version, target.package_manager, "unknown", None, None, error=str(exc))
        except (OSError, subprocess.TimeoutExpired) as exc:
            return UpdateResult(target.target, target.name, False, True, target.os_name, target.os_version, target.package_manager, "error", None, None, error=type(exc).__name__)
        if code != 0:
            return UpdateResult(target.target, target.name, True, True, target.os_name, target.os_version, target.package_manager, "error", None, None, error="apt simulation failed")
        packages, held, conflicts, removals = _parse_apt(stdout, stderr)
        digest = hashlib.sha256((stdout + "\n" + stderr).encode("utf-8", "replace")).hexdigest()
        return UpdateResult(target.target, target.name, True, True, target.os_name, target.os_version, target.package_manager, "updates_available" if packages else "current", len(packages), sum(item.security is True for item in packages), packages, held, conflicts, removals, utc_now(), None, 21600, digest, True)

    def check(self, target_id: str, *, force: bool = False) -> UpdateResult:
        target = self.target_map().get(target_id)
        if target is None or not _TARGET.fullmatch(target_id):
            raise ValidationError("target is not an authorized update target")
        cached = self._cache.get(target_id)
        if cached and not force and self._clock() - cached[1] < cached[0].stale_after_seconds:
            return cached[0]
        result = self._check_uncached(target)
        self._cache[target_id] = (result, self._clock())
        return result

    def all(self) -> list[dict[str, Any]]:
        return [self.check(target.target).as_dict() for target in self._targets()]

    def dry_run(self, target_id: str, *, confirmed: bool) -> dict[str, Any]:
        if confirmed is not True:
            raise ValidationError("dry run requires explicit confirmation")
        current = self.check(target_id)
        cached = self._cache.get(target_id)
        if not current.dry_run_supported or cached is None or self._clock() - cached[1] >= current.stale_after_seconds:
            return DryRunResult(target_id, True, False, False, current.plan_digest, error="a fresh successful update check is required").as_dict()
        latest = self._check_uncached(self.target_map()[target_id])
        if latest.plan_digest != current.plan_digest:
            self._cache[target_id] = (latest, self._clock())
            return DryRunResult(target_id, True, False, False, latest.plan_digest, error="update plan changed; dry run is stale").as_dict()
        safe = not latest.removals and not latest.conflicts and not latest.held_packages
        return DryRunResult(target_id, True, True, safe, latest.plan_digest, latest.packages, latest.held_packages, latest.conflicts, latest.removals, utc_now(), None if safe else "plan contains warnings").as_dict()


def make_targets(host: Mapping[str, Any], containers: Sequence[Mapping[str, Any]]) -> list[ProbeTarget]:
    # A Proxmox node is Debian-based, but the probe remains read-only and will
    # still report an explicit error if apt is not installed or permitted.
    targets = [ProbeTarget("host", str(host.get("name", "Proxmox host")), None, str(host.get("os_name", "Debian")), str(host.get("os_version", "unknown")), host.get("package_manager") or "apt")]
    for item in containers:
        cid = int(item["container_id"])
        targets.append(ProbeTarget(f"container:{cid}", str(item.get("name", cid)), cid, str(item.get("os_name", "unknown")), str(item.get("os_version", "unknown")), item.get("package_manager")))
    return targets
