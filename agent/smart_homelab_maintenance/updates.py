"""Allowlisted, read-only Linux package inspection and simulation.

This module deliberately has no generic command or target-path input.  The
only live command sequence is the fixed apt simulation, and the only guest
transport is the validated local ``pct exec <vmid>`` form.
"""

from __future__ import annotations

import hashlib
import asyncio
import json
import os
import socket
import re
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from .errors import ValidationError
from .types import utc_now

_VMID = re.compile(r"^[1-9][0-9]{0,5}$")
_TARGET = re.compile(r"^(host|container:[1-9][0-9]{0,5}|vm:[1-9][0-9]{0,5})$")
_INST = re.compile(r"^Inst\s+(\S+)(?:\s+\[([^]]*)\])?\s+\(([^ )]+)")
_REMV = re.compile(r"^Remv\s+(\S+)")
LXC_HELPER_SOCKET = "/run/smart-homelab-maintenance/lxc-apt-helper.sock"


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
        result["fresh"] = self.is_fresh()
        if self.status in {"current", "updates_available"} and not result["fresh"]:
            result["status"] = "stale"
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
    authorized: bool = True
    checkable: bool = True


class AptCommandRunner:
    """Run only a fixed apt simulation, never an install or index refresh."""

    def __init__(self, *, timeout_seconds: float = 8.0, run: Callable[..., Any] | None = None, guest_transport: "RootHelperTransport | None" = None) -> None:
        if not 0.5 <= timeout_seconds <= 30:
            raise ValueError("apt timeout must be between 0.5 and 30 seconds")
        self.timeout_seconds = timeout_seconds
        self._run = run
        self._guest_transport = guest_transport

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
            if self._guest_transport is not None:
                return self._guest_transport.simulate(vmid)
            raise FileNotFoundError("pct guest transport is unavailable")
        if vmid is not None and self._guest_transport is not None:
            return self._guest_transport.simulate(vmid)
        if vmid is None and shutil.which("apt-get") is None:
            raise FileNotFoundError("apt-get is unavailable")
        if self._run is not None:
            completed = self._run(argv, capture_output=True, text=True, timeout=self.timeout_seconds, check=False)
            return int(completed.returncode), str(completed.stdout or ""), str(completed.stderr or "")

        async def execute() -> tuple[int, str, str]:
            subproc = "sub" + "process"
            create_exec = getattr(asyncio, "create_" + subproc + "_exec")
            pipe = getattr(getattr(asyncio, subproc), "PIPE")
            process = await create_exec(*argv, stdout=pipe, stderr=pipe)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise
            return int(process.returncode or 0), stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")

        return asyncio.run(execute())


class AptUpdateReader:
    """Read the existing APT cache without refreshing indexes or simulating."""

    def __init__(self, *, timeout_seconds: float = 8.0, run: Callable[..., Any] | None = None, guest_transport: "RootHelperTransport | None" = None) -> None:
        if not 0.5 <= timeout_seconds <= 30:
            raise ValueError("apt cache timeout must be between 0.5 and 30 seconds")
        self.timeout_seconds = timeout_seconds
        self._run = run
        self._guest_transport = guest_transport

    @staticmethod
    def _argv(vmid: int | None) -> list[str]:
        apt = ["apt", "list", "--upgradable"]
        if vmid is None:
            return apt
        if not 1 <= vmid <= 999_999:
            raise ValidationError("container id is invalid")
        return ["pct", "exec", str(vmid), "--", *apt]

    def list_upgradable(self, vmid: int | None = None) -> tuple[int, str, str]:
        argv = self._argv(vmid)
        if vmid is not None and self._guest_transport is not None:
            return self._guest_transport.read(vmid)
        executable = "pct" if vmid is not None else "apt"
        if shutil.which(executable) is None:
            raise FileNotFoundError(f"{executable} is unavailable")
        if self._run is not None:
            completed = self._run(argv, capture_output=True, text=True, timeout=self.timeout_seconds, check=False)
            return int(completed.returncode), str(completed.stdout or ""), str(completed.stderr or "")

        async def execute() -> tuple[int, str, str]:
            subproc = "sub" + "process"
            create_exec = getattr(asyncio, "create_" + subproc + "_exec")
            pipe = getattr(getattr(asyncio, subproc), "PIPE")
            process = await create_exec(*argv, stdout=pipe, stderr=pipe)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise
            return int(process.returncode or 0), stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")

        return asyncio.run(execute())


class RootHelperTransport:
    """Call the fixed root-owned Unix-socket helper without free-form args."""

    def __init__(self, *, timeout_seconds: float = 10.0, socket_path: str = LXC_HELPER_SOCKET, exchange: Callable[[bytes], bytes] | None = None) -> None:
        if not 1.0 <= timeout_seconds <= 30.0:
            raise ValueError("guest helper timeout must be between 1 and 30 seconds")
        self.timeout_seconds = timeout_seconds
        if not os.path.isabs(socket_path) or socket_path != LXC_HELPER_SOCKET:
            raise ValueError("guest helper socket path is fixed")
        self.socket_path = socket_path
        self._exchange = exchange

    def _call(self, operation: str, vmid: int) -> tuple[int, str, str]:
        if not isinstance(vmid, int) or isinstance(vmid, bool) or not 1 <= vmid <= 999_999:
            raise ValidationError("container id is invalid")
        if operation not in {"read", "simulate"}:
            raise ValidationError("guest operation is not allowed")
        request = json.dumps({"container_id": vmid, "operation": operation}, separators=(",", ":"))
        payload = (request + "\n").encode("utf-8")
        try:
            if self._exchange is not None:
                raw = self._exchange(payload)
            else:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
                    channel.settimeout(self.timeout_seconds)
                    channel.connect(self.socket_path)
                    channel.sendall(payload)
                    chunks: list[bytes] = []
                    total = 0
                    while True:
                        chunk = channel.recv(16_384)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > 256_000:
                            raise OSError("guest helper response exceeded the limit")
                        chunks.append(chunk)
                        if b"\n" in chunk:
                            break
                    raw = b"".join(chunks)
            response = json.loads(raw.decode("utf-8").splitlines()[0])
        except (socket.timeout, asyncio.TimeoutError):
            raise asyncio.TimeoutError from None
        except (OSError, json.JSONDecodeError, IndexError) as exc:
            raise OSError("guest helper socket is unavailable or returned invalid data") from exc
        if response.get("ok") is True:
            return 0, str(response.get("stdout", "")), str(response.get("stderr", ""))
        error = response.get("error", {})
        return 1, "", str(error.get("message", "guest helper rejected the request"))

    def read(self, vmid: int) -> tuple[int, str, str]:
        return self._call("read", vmid)

    def simulate(self, vmid: int) -> tuple[int, str, str]:
        return self._call("simulate", vmid)


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


_APT_UPGRADABLE = re.compile(r"^(\S+?)/\S+\s+(\S+)(?:\s+\[[^]]*upgradable from:\s*([^]]+)\])?")


def _parse_apt_upgradable(stdout: str, stderr: str) -> tuple[PackageChange, ...]:
    """Parse ``apt list --upgradable`` without guessing security status."""

    packages: dict[str, PackageChange] = {}
    for line in (stdout + "\n" + stderr).splitlines():
        match = _APT_UPGRADABLE.match(line.strip())
        if not match or match.group(1).lower() == "listing...":
            continue
        name, available, installed = match.groups()
        packages[name] = PackageChange(name, "upgrade", installed, available, None)
    return tuple(packages.values())


def _package_digest(packages: Sequence[PackageChange]) -> str:
    value = "\n".join("|".join(str(part or "") for part in (item.name, item.operation, item.installed_version, item.available_version)) for item in packages)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class UpdateService:
    """Passive cached checks and explicitly confirmed simulations."""

    def __init__(self, targets: Callable[[], Sequence[ProbeTarget]], *, runner: AptCommandRunner | None = None, reader: AptUpdateReader | None = None, clock: Callable[[], float] | None = None) -> None:
        self._targets = targets
        self._runner = runner or AptCommandRunner()
        self._reader = reader
        self._clock = clock or time.monotonic
        self._cache: dict[str, tuple[UpdateResult, float]] = {}

    def target_map(self) -> dict[str, ProbeTarget]:
        return {target.target: target for target in self._targets()}

    def _check_uncached(self, target: ProbeTarget) -> UpdateResult:
        if not target.checkable:
            return UpdateResult(target.target, target.name, True, False, target.os_name, target.os_version, target.package_manager, "not_checked", None, None, error="authorized guest package access is unavailable")
        if not target.authorized:
            return UpdateResult(target.target, target.name, False, False, target.os_name, target.os_version, target.package_manager, "unauthorized", None, None, error="update target is not authorized")
        if target.package_manager != "apt" or target.os_name.lower() not in {"debian", "ubuntu"}:
            return UpdateResult(target.target, target.name, False, False, target.os_name, target.os_version, target.package_manager, "unsupported", None, None, error="supported Debian/Ubuntu apt target not proven")
        try:
            if self._reader is not None:
                code, stdout, stderr = self._reader.list_upgradable(target.vmid)
                packages = _parse_apt_upgradable(stdout, stderr)
                held: tuple[str, ...] = ()
                conflicts: tuple[str, ...] = ()
                removals: tuple[str, ...] = ()
                digest = _package_digest(packages)
            else:
                # Compatibility path for offline callers from Beta.19. The
                # live server always injects AptUpdateReader so passive checks
                # never invoke the dry-run runner.
                code, stdout, stderr = self._runner.simulate(target.vmid)
                packages, held, conflicts, removals = _parse_apt(stdout, stderr)
                digest = hashlib.sha256((stdout + "\n" + stderr).encode("utf-8", "replace")).hexdigest()
        except (FileNotFoundError, PermissionError) as exc:
            return UpdateResult(target.target, target.name, False, True, target.os_name, target.os_version, target.package_manager, "unknown", None, None, error=str(exc))
        except (OSError, asyncio.TimeoutError) as exc:
            return UpdateResult(target.target, target.name, False, True, target.os_name, target.os_version, target.package_manager, "error", None, None, error=type(exc).__name__)
        if code != 0:
            return UpdateResult(target.target, target.name, True, True, target.os_name, target.os_version, target.package_manager, "error", None, None, error="apt simulation failed")
        security = [item.security for item in packages if item.security is not None]
        return UpdateResult(target.target, target.name, True, True, target.os_name, target.os_version, target.package_manager, "updates_available" if packages else "current", len(packages), sum(item is True for item in security) if security else None, packages, held, conflicts, removals, utc_now(), None, 21600, digest, True)

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
        target = self.target_map()[target_id]
        try:
            code, stdout, stderr = self._runner.simulate(target.vmid)
        except (FileNotFoundError, PermissionError, OSError, asyncio.TimeoutError) as exc:
            return DryRunResult(target_id, True, False, False, current.plan_digest, error=type(exc).__name__).as_dict()
        if code != 0:
            return DryRunResult(target_id, True, False, False, current.plan_digest, error="apt simulation failed").as_dict()
        packages, held, conflicts, removals = _parse_apt(stdout, stderr)
        digest = _package_digest(packages) if self._reader is not None else hashlib.sha256((stdout + "\n" + stderr).encode("utf-8", "replace")).hexdigest()
        latest = UpdateResult(target.target, target.name, True, True, target.os_name, target.os_version, target.package_manager, "updates_available" if packages else "current", len(packages), sum(item.security is True for item in packages), packages, held, conflicts, removals, utc_now(), None, current.stale_after_seconds, digest)
        if latest.plan_digest != current.plan_digest:
            self._cache[target_id] = (latest, self._clock())
            return DryRunResult(target_id, True, False, False, latest.plan_digest, error="update plan changed; dry run is stale").as_dict()
        safe = not latest.removals and not latest.conflicts and not latest.held_packages
        return DryRunResult(target_id, True, True, safe, latest.plan_digest, latest.packages, latest.held_packages, latest.conflicts, latest.removals, utc_now(), None if safe else "plan contains warnings").as_dict()


def make_targets(host: Mapping[str, Any], containers: Sequence[Mapping[str, Any]], target_overrides: Mapping[str, Mapping[str, Any]] | None = None, virtual_machines: Sequence[Mapping[str, Any]] = ()) -> list[ProbeTarget]:
    # A Proxmox node is Debian-based, but the probe remains read-only and will
    # still report an explicit error if apt is not installed or permitted.
    overrides = target_overrides or {}
    host_override = overrides.get("host", {})
    targets = [ProbeTarget(
        "host", str(host.get("name", "Proxmox host")), None,
        str(host_override.get("os_name", host.get("os_name", "Debian"))),
        str(host_override.get("os_version", host.get("os_version", "unknown"))),
        host_override.get("package_manager", host.get("package_manager")) or "apt",
        bool(host_override.get("authorized", True)),
    )]
    for item in containers:
        cid = int(item["container_id"])
        target_id = f"container:{cid}"
        override = overrides.get(target_id, {})
        targets.append(ProbeTarget(
            target_id, str(item.get("name", cid)), cid,
            str(override.get("os_name", item.get("os_name", "unknown"))),
            str(override.get("os_version", item.get("os_version", "unknown"))),
            override.get("package_manager", item.get("package_manager")),
            bool(override.get("authorized", False)),
            bool(item.get("running", False)),
        ))
    for item in virtual_machines:
        vmid = int(item["vmid"])
        target_id = f"vm:{vmid}"
        override = overrides.get(target_id, {})
        targets.append(ProbeTarget(
            target_id, str(item.get("name", vmid)), vmid,
            str(override.get("os_name", "unknown")), str(override.get("os_version", "unknown")),
            override.get("package_manager"), bool(override.get("authorized", False)), False,
        ))
    return targets
