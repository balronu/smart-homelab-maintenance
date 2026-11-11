"""Allowlisted Linux package inspection, simulation, and opt-in updates.

This module deliberately has no generic command or target-path input. The
guest transport is the validated local ``pct exec <vmid>`` form; real updates
remain separately authorized and disabled by default.
"""

from __future__ import annotations

import hashlib
import asyncio
import json
import os
import socket
import re
import shutil
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from .errors import ValidationError
from .jobs import JobRepository
from .permissions import PermissionStore
from .types import JobPhase, JobRequest, JobState, Verification, utc_now

_VMID = re.compile(r"^[1-9][0-9]{0,5}$")
_TARGET = re.compile(r"^(host|container:[1-9][0-9]{0,5}|vm:[1-9][0-9]{0,5})$")
_INST = re.compile(r"^Inst\s+(\S+)(?:\s+\[([^]]*)\])?\s+\(([^ )]+)")
_REMV = re.compile(r"^Remv\s+(\S+)")
LXC_HELPER_SOCKET = "/run/smart-homelab-maintenance/lxc-apt-helper.sock"


class GuestHelperUnavailableError(OSError):
    """The opt-in LXC helper is absent or returned an invalid response."""


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
    simulation_method: str | None = None
    simulation_reason: str | None = None
    update_authorized: bool = False
    update_supported: bool = False
    update_reason: str | None = None
    simulation_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["packages"] = [asdict(item) for item in self.packages]
        result["held_packages"] = list(self.held_packages)
        result["conflicts"] = list(self.conflicts)
        result["removals"] = list(self.removals)
        result["fresh"] = self.is_fresh()
        result["authorized"] = bool(self.simulation_authorized)
        if self.status in {"current", "updates_available"} and not result["fresh"]:
            result["status"] = "stale"
        return result

    @property
    def fresh(self) -> bool:
        return self.is_fresh()

    @property
    def authorized(self) -> bool:
        return bool(self.simulation_authorized)

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
    update_authorized: bool = False


class AptCommandRunner:
    """Run fixed APT commands; real updates require a separate opt-in path."""

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

    def probe(self, vmid: int) -> dict[str, Any]:
        if self._guest_transport is None:
            raise GuestHelperUnavailableError("LXC eligibility helper is unavailable")
        return self._guest_transport.probe(vmid)

    def update(self, vmid: int) -> tuple[int, str, str]:
        if not isinstance(vmid, int) or isinstance(vmid, bool) or not 1 <= vmid <= 999_999:
            raise ValidationError("container id is invalid")
        if self._guest_transport is None:
            raise FileNotFoundError("LXC update helper is unavailable")
        return self._guest_transport.update(vmid)

    def inspect(self, vmid: int) -> dict[str, Any]:
        if self._guest_transport is None:
            raise GuestHelperUnavailableError("LXC inspection helper is unavailable")
        return self._guest_transport.inspect(vmid)


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

    def _call_response(self, operation: str, vmid: int) -> dict[str, Any]:
        if not isinstance(vmid, int) or isinstance(vmid, bool) or not 1 <= vmid <= 999_999:
            raise ValidationError("container id is invalid")
        if operation not in {"read", "simulate", "update", "inspect", "probe"}:
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
            raise GuestHelperUnavailableError(
                "LXC simulation helper is unavailable or returned an invalid response"
            ) from exc
        if response.get("ok") is True:
            return response
        error = response.get("error", {})
        return {"ok": False, "stdout": "", "stderr": str(error.get("message", "guest helper rejected the request"))}

    def _call(self, operation: str, vmid: int) -> tuple[int, str, str]:
        response = self._call_response(operation, vmid)
        return (0 if response.get("ok") is True else 1, str(response.get("stdout", "")), str(response.get("stderr", "")))

    def read(self, vmid: int) -> tuple[int, str, str]:
        return self._call("read", vmid)

    def simulate(self, vmid: int) -> tuple[int, str, str]:
        return self._call("simulate", vmid)

    def update(self, vmid: int) -> tuple[int, str, str, list[dict[str, Any]]]:
        response = self._call_response("update", vmid)
        return (0 if response.get("ok") is True else 1, str(response.get("stdout", "")), str(response.get("stderr", "")), list(response.get("steps", [])))

    def probe(self, vmid: int) -> dict[str, Any]:
        response = self._call_response("probe", vmid)
        if response.get("ok") is not True:
            raise ValidationError(str(response.get("stderr", "eligibility probe failed")))
        return response

    def inspect(self, vmid: int) -> dict[str, Any]:
        """Collect fixed, read-only package forensic observations."""
        response = self._call_response("inspect", vmid)
        if response.get("ok") is not True:
            raise GuestHelperUnavailableError(str(response.get("stderr", "guest inspection failed")))
        return response


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


def _inspection_packages(response: Mapping[str, Any]) -> dict[str, str]:
    observations = response.get("observations") if isinstance(response, Mapping) else None
    package_observation = observations.get("packages", {}) if isinstance(observations, Mapping) else {}
    if not isinstance(package_observation, Mapping) or package_observation.get("returncode") != 0:
        return {}
    result: dict[str, str] = {}
    for line in str(package_observation.get("stdout", "")).splitlines():
        name, separator, version = line.partition("\t")
        if separator and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.:-]*", name) and version:
            result[name] = version[:256]
    return result


_APT_UPGRADABLE = re.compile(
    r"^(\S+?)/\S+\s+(\S+)"
    r"(?:\s+(?!\[)\S+)?"
    r"(?:\s+\[[^]]*upgradable from:\s*([^]]+)\])?"
)


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
    # ``apt list --upgradable`` and ``apt-get --simulate`` are equivalent
    # sources for the package plan, but do not promise the same ordering.
    # Compare a canonical, sorted representation so ordering alone cannot
    # turn an unchanged plan into a stale-plan rejection.
    canonical = sorted(
        (item.name, item.operation, item.installed_version or "", item.available_version or "")
        for item in packages
    )
    value = "\n".join("|".join(part) for part in canonical)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class UpdateService:
    """Passive checks plus explicitly confirmed, separately authorized updates."""

    def __init__(self, targets: Callable[[], Sequence[ProbeTarget]], *, runner: AptCommandRunner | None = None, reader: AptUpdateReader | None = None, clock: Callable[[], float] | None = None, execution_enabled: bool = False, permission_store: PermissionStore | None = None, jobs: JobRepository | None = None) -> None:
        self._targets = targets
        self._runner = runner or AptCommandRunner()
        self._reader = reader
        self._clock = clock or time.monotonic
        self._cache: dict[str, tuple[UpdateResult, float]] = {}
        self._active_simulations: set[str] = set()
        self.execution_enabled = execution_enabled
        self._permission_store = permission_store
        self._jobs = jobs

    def target_map(self) -> dict[str, ProbeTarget]:
        targets = {target.target: target for target in self._targets()}
        if self._permission_store is None:
            return targets
        entries = self._permission_store.read()
        for target_id, target in list(targets.items()):
            if target_id.startswith("container:"):
                entry = entries.get(target_id.split(":", 1)[1], {})
                # A successful eligibility probe persists the authoritative
                # OS/APT evidence beside the grant.  Reapply that evidence to
                # the live target on every read; otherwise a Proxmox inventory
                # record with unknown metadata remains ``unsupported`` even
                # though the permission write succeeded.
                targets[target_id] = ProbeTarget(
                    target.target,
                    target.name,
                    target.vmid,
                    str(entry.get("os_name", target.os_name)),
                    str(entry.get("os_version", target.os_version)),
                    entry.get("package_manager", target.package_manager),
                    bool(entry.get("simulation_authorized", entry.get("authorized", target.authorized))),
                    target.checkable,
                    bool(entry.get("update_authorized", target.update_authorized)),
                )
        return targets

    def set_permissions(self, target_id: str, *, simulation_authorized: bool, update_authorized: bool, confirmed: bool) -> dict[str, Any]:
        if confirmed is not True or self._permission_store is None:
            raise ValidationError("explicit confirmation and a protected permission store are required")
        target = {target.target: target for target in self._targets()}.get(target_id)
        if target is None or not target_id.startswith("container:") or not target.checkable:
            raise ValidationError("only running LXC targets may be authorized")
        if update_authorized and not simulation_authorized:
            raise ValidationError("real update authorization requires simulation authorization")
        entries = self._permission_store.read()
        raw_id = target_id.split(":", 1)[1]
        existing = entries.get(raw_id, {})
        # Revocation must remain possible even if discovery is temporarily
        # incomplete; it never grants access and preserves existing metadata.
        if not simulation_authorized and not update_authorized:
            metadata = {key: existing.get(key) for key in ("os_name", "os_version", "package_manager")}
            result = self._permission_store.set_permissions(target_id, simulation_authorized=False, update_authorized=False, metadata=metadata)
            self._cache.pop(target_id, None)
            return result
        try:
            probe = self._runner.probe(target.vmid)
        except AttributeError as exc:
            raise ValidationError("target eligibility probe is unavailable") from exc
        except (GuestHelperUnavailableError, FileNotFoundError, PermissionError, OSError, asyncio.TimeoutError) as exc:
            raise ValidationError("target eligibility could not be verified") from exc
        if not isinstance(probe, dict) or probe.get("running") is not True or probe.get("supported") is not True:
            raise ValidationError("target is not a proven Debian/Ubuntu apt LXC")
        os_name = str(probe.get("os_name", ""))
        os_version = str(probe.get("os_version", ""))
        package_manager = str(probe.get("package_manager", ""))
        if os_name.lower() not in {"debian", "ubuntu"} or not os_version or package_manager != "apt":
            raise ValidationError("target is not a proven Debian/Ubuntu apt LXC")
        result = self._permission_store.set_permissions(target_id, simulation_authorized=simulation_authorized, update_authorized=update_authorized, metadata={"os_name": os_name, "os_version": os_version, "package_manager": package_manager})
        self._cache.pop(target_id, None)
        return result

    def _check_uncached(self, target: ProbeTarget) -> UpdateResult:
        if target.target.startswith("vm:"):
            return UpdateResult(target.target, target.name, True, False, target.os_name, target.os_version, target.package_manager, "not_checked", None, None, error="VM guest package transport is unavailable; no simulation was run", simulation_method=None, simulation_reason="vm-guest-transport-unavailable")
        if not target.checkable:
            return UpdateResult(target.target, target.name, True, False, target.os_name, target.os_version, target.package_manager, "not_checked", None, None, error="authorized guest package access is unavailable", simulation_method="lxc-apt-helper", simulation_reason="target-not-running-or-not-checked")
        if not target.authorized:
            return UpdateResult(target.target, target.name, False, False, target.os_name, target.os_version, target.package_manager, "unauthorized", None, None, error="update target is not authorized", simulation_method="lxc-apt-helper", simulation_reason="explicit-target-authorization-required")
        if target.package_manager != "apt" or target.os_name.lower() not in {"debian", "ubuntu"}:
            return UpdateResult(target.target, target.name, False, False, target.os_name, os_version=target.os_version, package_manager=target.package_manager, status="unsupported", available_count=None, security_count=None, error="supported Debian/Ubuntu apt target not proven", simulation_method="lxc-apt-helper", simulation_reason="debian-or-ubuntu-apt-not-proven")
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
        except GuestHelperUnavailableError as exc:
            return UpdateResult(
                target.target, target.name, False, True, target.os_name, target.os_version,
                target.package_manager, "unknown", None, None,
                error="LXC simulation helper is unavailable",
                simulation_method="lxc-apt-helper", simulation_reason="helper-unavailable",
            )
        except (FileNotFoundError, PermissionError) as exc:
            return UpdateResult(target.target, target.name, False, True, target.os_name, target.os_version, target.package_manager, "unknown", None, None, error=str(exc))
        except (OSError, asyncio.TimeoutError) as exc:
            return UpdateResult(target.target, target.name, False, True, target.os_name, target.os_version, target.package_manager, "error", None, None, error=type(exc).__name__)
        if code != 0:
            return UpdateResult(target.target, target.name, True, True, target.os_name, target.os_version, target.package_manager, "error", None, None, error="apt simulation failed")
        security = [item.security for item in packages if item.security is not None]
        update_authorized = bool(target.target.startswith("container:") and target.update_authorized)
        update_supported = bool(self.execution_enabled and update_authorized and not held and not conflicts and not removals)
        update_reason = None if update_supported else ("explicit-update-authorization-required" if not update_authorized else "update-execution-disabled")
        return UpdateResult(target.target, target.name, True, True, target.os_name, target.os_version, target.package_manager, "updates_available" if packages else "current", len(packages), sum(item is True for item in security) if security else None, packages, held, conflicts, removals, utc_now(), None, 21600, digest, True, "local-apt" if target.target == "host" else "lxc-apt-helper", None, target.update_authorized, update_supported, update_reason, target.authorized)

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
        target = self.target_map().get(target_id)
        if target is None or not _TARGET.fullmatch(target_id):
            raise ValidationError("target is not an authorized update target")
        if target_id in self._active_simulations:
            return DryRunResult(target_id, True, False, False, None, error="simulation already running for target").as_dict()
        current = self.check(target_id)
        if target_id.startswith("vm:"):
            return DryRunResult(target_id, True, False, False, current.plan_digest, error="VM guest package transport is unavailable; no simulation was run").as_dict()
        cached = self._cache.get(target_id)
        if not current.dry_run_supported or cached is None or self._clock() - cached[1] >= current.stale_after_seconds:
            return DryRunResult(target_id, True, False, False, current.plan_digest, error="a fresh successful update check is required").as_dict()
        self._active_simulations.add(target_id)
        try:
            code, stdout, stderr = self._runner.simulate(target.vmid)
        except (FileNotFoundError, PermissionError, OSError, asyncio.TimeoutError) as exc:
            self._active_simulations.discard(target_id)
            return DryRunResult(target_id, True, False, False, current.plan_digest, error=type(exc).__name__).as_dict()
        try:
            if code != 0:
                return DryRunResult(target_id, True, False, False, current.plan_digest, error="apt simulation failed").as_dict()
            packages, held, conflicts, removals = _parse_apt(stdout, stderr)
            digest = _package_digest(packages) if self._reader is not None else hashlib.sha256((stdout + "\n" + stderr).encode("utf-8", "replace")).hexdigest()
            latest = UpdateResult(target.target, target.name, True, True, target.os_name, target.os_version, target.package_manager, "updates_available" if packages else "current", len(packages), sum(item.security is True for item in packages), packages, held, conflicts, removals, utc_now(), None, current.stale_after_seconds, digest, True, "local-apt" if target_id == "host" else "lxc-apt-helper", None, target.update_authorized, False, "update-execution-disabled", target.authorized)
            if latest.plan_digest != current.plan_digest:
                self._cache[target_id] = (latest, self._clock())
                return DryRunResult(target_id, True, False, False, latest.plan_digest, error="update plan changed; dry run is stale").as_dict()
            safe = not latest.removals and not latest.conflicts and not latest.held_packages
            return DryRunResult(target_id, True, True, safe, latest.plan_digest, latest.packages, latest.held_packages, latest.conflicts, latest.removals, utc_now(), None if safe else "plan contains warnings").as_dict()
        finally:
            self._active_simulations.discard(target_id)

    def execute_update(self, target_id: str, *, confirmed: bool, install_confirmed: bool = False, plan_digest: str | None) -> dict[str, Any]:
        if confirmed is not True or install_confirmed is not True:
            raise ValidationError("explicit simulation and installation confirmations are both required")
        if not self.execution_enabled:
            return {"target": target_id, "success": False, "safe": False, "error": "update execution is disabled"}
        target = self.target_map().get(target_id)
        if target is None or not _TARGET.fullmatch(target_id) or not target_id.startswith("container:"):
            return {"target": target_id, "success": False, "safe": False, "error": "only authorized LXC targets may be updated"}
        if not target.update_authorized:
            return {"target": target_id, "success": False, "safe": False, "error": "target is not authorized for real updates"}
        if self._jobs is not None and self._jobs.has_unresolved_target(target_id):
            return {"target": target_id, "success": False, "safe": False,
                    "error": "another update is active or requires manual recovery",
                    "status": "manual_recovery_required"}
        # Use the already-fetched, user-confirmed plan for the HTTP admission
        # decision. A fresh helper check here would defeat async acceptance;
        # the worker repeats it before any mutating operation.
        current = self.check(target_id)
        if current.status != "updates_available" or not current.is_fresh():
            return {"target": target_id, "success": False, "safe": False, "error": "fresh updates are not available"}
        if current.plan_digest != plan_digest:
            return {"target": target_id, "success": False, "safe": False, "error": "update plan changed; confirmation is stale", "plan_digest": current.plan_digest}
        if current.held_packages or current.conflicts or current.removals:
            return {"target": target_id, "success": False, "safe": False, "error": "update plan contains held, conflicting, or removing packages"}
        if target_id in self._active_simulations:
            return {"target": target_id, "success": False, "safe": False, "error": "another update is already running for target"}
        job_id: str | None = None
        if self._jobs is not None:
            try:
                job_id = self._jobs.create(JobRequest(
                    target=target_id,
                    operation="update",
                    expected_version=None,
                    idempotency_key=f"{target_id}:{current.plan_digest}",
                    confirmation_hash=current.plan_digest,
                ))
                self._jobs.transition(job_id, JobState.PREFLIGHT, phase=JobPhase.PREFLIGHT, progress=10, message="fresh update plan validated")
                self._jobs.append_log(job_id, "fresh plan and target authorization validated")
            except Exception as exc:
                return {"target": target_id, "success": False, "safe": False, "error": "update job could not be created", "job_error": type(exc).__name__}
        self._active_simulations.add(target_id)
        try:
            if job_id and self._jobs:
                # Persist and acknowledge the job before any guest helper call.
                # The HA client has a deliberately short transport timeout;
                # final inspection/simulation belongs to the worker lifetime.
                self._jobs.append_log(job_id, "update job accepted; APT worker queued")
                worker = threading.Thread(
                    target=self._run_update_job,
                    args=(job_id, target, current.plan_digest),
                    name=f"smh-update-{target.vmid}",
                    daemon=True,
                )
                worker.start()
                return {
                    "target": target_id,
                    "operation": "update",
                    "success": True,
                    "accepted": True,
                    "safe": True,
                    "job_id": job_id,
                    # Keep the public response contract stable: accepted is
                    # the asynchronous running lifecycle even while the
                    # persisted row remains in preflight until the worker
                    # completes final validation.
                    "status": "running",
                    "plan_digest": current.plan_digest,
                    "message": "update job accepted; poll the job endpoint for completion",
                }
            # A persistent job repository is required for real execution.  It
            # provides duplicate protection and restart-safe recovery.
            return {"target": target_id, "success": False, "safe": False, "error": "persistent job tracking is required for update execution", "job_id": job_id}
        except (FileNotFoundError, PermissionError, OSError, asyncio.TimeoutError) as exc:
            if job_id and self._jobs:
                self._jobs.transition(job_id, JobState.MANUAL_RECOVERY, phase=JobPhase.RECOVERY, progress=100, message="execution status is uncertain; manual recovery required", error_code="execution_status_unknown")
                self._jobs.append_log(job_id, "preflight transport or timeout failure; no automatic retry was attempted", level="warning")
            return {"target": target_id, "operation": "update", "success": False, "safe": False, "error": type(exc).__name__, "status": "manual_recovery_required", "job_id": job_id}
        finally:
            # The worker owns this guard after dispatch; failed preflight must
            # release it here so a safe retry is not falsely blocked.
            if not job_id or not self._jobs or not self._jobs.has_unresolved_target(target_id):
                self._active_simulations.discard(target_id)

    def _run_update_job(self, job_id: str, target: ProbeTarget, plan_digest: str | None) -> None:
        """Run the mutating helper outside the HTTP request lifetime."""
        target_id = target.target
        try:
            assert self._jobs is not None
            # All guest inspection and final simulation remain fail-closed, but
            # run after the persistent job acknowledgement so HA never waits
            # for a slow helper during the execute request.
            fresh = self.check(target_id, force=True)
            if fresh.status != "updates_available" or not fresh.is_fresh():
                self._jobs.transition(job_id, JobState.BLOCKED, phase=JobPhase.PREFLIGHT, progress=20, message="fresh update plan is unavailable", error_code="fresh_plan_unavailable")
                return
            if fresh.plan_digest != plan_digest:
                self._jobs.transition(job_id, JobState.BLOCKED, phase=JobPhase.PREFLIGHT, progress=20, message="plan changed before execution", error_code="stale_plan")
                return
            inspect_method = getattr(self._runner, "inspect", None)
            inspection = inspect_method(target.vmid) if callable(inspect_method) else {"observations": {}}
            baseline = _inspection_packages(inspection)
            self._jobs.set_execution_context(job_id, plan_digest=plan_digest or "", baseline_packages=baseline)
            simulation_code, simulation_stdout, simulation_stderr = self._runner.simulate(target.vmid)
            if simulation_code != 0:
                self._jobs.transition(job_id, JobState.FAILED, phase=JobPhase.PREFLIGHT, progress=20, message="pre-execution simulation failed", error_code="simulation_failed")
                return
            simulated, held, conflicts, removals = _parse_apt(simulation_stdout, simulation_stderr)
            simulation_digest = _package_digest(simulated) if self._reader is not None else hashlib.sha256((simulation_stdout + "\n" + simulation_stderr).encode("utf-8", "replace")).hexdigest()
            if simulation_digest != plan_digest:
                self._jobs.transition(job_id, JobState.BLOCKED, phase=JobPhase.PREFLIGHT, progress=20, message="plan changed before execution", error_code="stale_plan")
                return
            if held or conflicts or removals:
                self._jobs.transition(job_id, JobState.BLOCKED, phase=JobPhase.PREFLIGHT, progress=20, message="simulation contains unsafe changes", error_code="unsafe_plan")
                return
            self._jobs.transition(job_id, JobState.RUNNING, phase=JobPhase.EXECUTION, progress=30, message="fixed APT update started")
            self._jobs.append_log(job_id, "apt update and no-remove upgrade started")
            update_result = self._runner.update(target.vmid)
            code, stdout, stderr = update_result[:3]
            steps = list(update_result[3]) if len(update_result) > 3 else [{"name": "apt-update"}, {"name": "apt-upgrade"}]
            postcheck = {"performed": False}
            postcheck_passed = True
            if code == 0 and self._reader is not None:
                try:
                    post_code, post_stdout, post_stderr = self._reader.list_upgradable(target.vmid)
                    remaining = _parse_apt_upgradable(post_stdout, post_stderr)
                    postcheck = {"performed": True, "returncode": post_code, "remaining_packages": len(remaining)}
                    postcheck_passed = post_code == 0
                except (FileNotFoundError, PermissionError, OSError, asyncio.TimeoutError) as exc:
                    postcheck = {"performed": True, "returncode": None, "error": type(exc).__name__}
                    postcheck_passed = False
            if code == 0 and postcheck_passed:
                self._jobs.transition(job_id, JobState.POSTCHECK, phase=JobPhase.POSTCHECK, progress=90, message="update command completed; postcheck required")
                self._jobs.complete(job_id, Verification(True, True, message="fixed APT update completed"), message="fixed APT update completed")
                self._jobs.append_log(job_id, "update completed and postcheck passed")
            else:
                self._jobs.transition(job_id, JobState.MANUAL_RECOVERY if code == 0 else JobState.FAILED, phase=JobPhase.RECOVERY, progress=100, message="postcheck failed" if code == 0 else "APT update failed", error_code="postcheck_failed" if code == 0 else "apt_failed")
                self._jobs.append_log(job_id, "postcheck failed" if code == 0 else "APT update failed", level="error")
        except (FileNotFoundError, PermissionError, OSError, asyncio.TimeoutError) as exc:
            self._jobs.transition(job_id, JobState.MANUAL_RECOVERY, phase=JobPhase.RECOVERY, progress=100, message="execution status is uncertain; manual recovery required", error_code="execution_status_unknown")
            self._jobs.append_log(job_id, "transport or timeout failure; no automatic retry was attempted", level="warning")
        except Exception as exc:  # pragma: no cover - defensive worker boundary
            self._jobs.transition(job_id, JobState.MANUAL_RECOVERY, phase=JobPhase.RECOVERY, progress=100, message="worker failed; manual recovery required", error_code="worker_failed", error_message=type(exc).__name__)
            self._jobs.append_log(job_id, "unexpected worker failure; no automatic retry was attempted", level="error")
        finally:
            self._active_simulations.discard(target_id)

    def cancel_job(self, job_id: str, *, confirmed: bool) -> dict[str, Any]:
        """Cancel only pre-mutation work; running helper jobs remain locked."""
        if confirmed is not True:
            raise ValidationError("explicit cancellation confirmation is required")
        if self._jobs is None:
            raise ValidationError("persistent job tracking is unavailable")
        return self._jobs.request_cancel(job_id)


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
        simulation_authorized = override.get("simulation_authorized", override.get("authorized", False))
        targets.append(ProbeTarget(
            target_id, str(item.get("name", cid)), cid,
            str(override.get("os_name", item.get("os_name", "unknown"))),
            str(override.get("os_version", item.get("os_version", "unknown"))),
            override.get("package_manager", item.get("package_manager")),
            bool(simulation_authorized),
            bool(item.get("running", False)),
            bool(override.get("update_authorized", False)),
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
