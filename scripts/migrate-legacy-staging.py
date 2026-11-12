#!/usr/bin/env python3
"""Explicit, fail-closed migration for pre-release-identity rollback staging.

This is an administrative exception for historical directories only.  It does
not participate in normal agent upgrades and never invents a release identity.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import stat
import sys
import time
from pathlib import Path


SCHEMA = 1
LEGACY_NAME = re.compile(r"agent\.(?:previous|failed)\.[0-9]+\.staging\Z")


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def manifest(path: Path) -> tuple[str, int, list[str], list[str]]:
    rows: list[str] = []
    symlinks: list[str] = []
    unsupported: list[str] = []
    for child in sorted(path.rglob("*")):
        relative = child.relative_to(path).as_posix()
        try:
            mode = child.lstat().st_mode
        except OSError as exc:
            unsupported.append(f"{relative}:{exc.__class__.__name__}")
            continue
        if stat.S_ISLNK(mode):
            symlinks.append(relative)
        elif stat.S_ISREG(mode):
            rows.append(f"F {hashlib.sha256(child.read_bytes()).hexdigest()} {relative}")
        elif not stat.S_ISDIR(mode):
            unsupported.append(relative)
    digest = hashlib.sha256(("\n".join(rows) + "\n").encode()).hexdigest()
    return digest, len(rows), symlinks, unsupported


def ancestors() -> set[int]:
    result = {os.getpid()}
    current = os.getpid()
    while current > 1:
        try:
            fields = (Path("/proc") / str(current) / "stat").read_text().split()
            current = int(fields[3])
        except (OSError, ValueError, IndexError):
            break
        result.add(current)
    return result


def process_refs(path: Path) -> list[dict[str, str]]:
    target = str(path.resolve())
    result: list[dict[str, str]] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) in ancestors():
            continue
        try:
            references = [os.path.realpath(proc / "cwd"), os.path.realpath(proc / "root")]
            references.extend(os.path.realpath(fd) for fd in (proc / "fd").iterdir() if fd.is_symlink())
            if any(item == target or item.startswith(target + os.sep) for item in references):
                command = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
                result.append({"pid": proc.name, "command": command[:240]})
        except (OSError, PermissionError):
            continue
    return result


def global_upgrade_refs() -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    pattern = re.compile(r"(?:upgrade-agent|update-agent)\.sh|agent\.(?:failed|previous)\.[^ ]+\.staging")
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) in ancestors():
            continue
        try:
            command = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
        except (OSError, PermissionError):
            continue
        if pattern.search(command):
            result.append({"pid": proc.name, "command": command[:240]})
    return result


def systemd_refs(path: Path) -> list[str]:
    target = str(path.resolve()).encode()
    result: list[str] = []
    for base in (Path("/etc/systemd/system"), Path("/etc/smart-homelab-maintenance")):
        if not base.exists():
            continue
        for child in base.rglob("*"):
            if not child.is_file() or child.is_symlink():
                continue
            try:
                if target in child.read_bytes():
                    result.append(str(child))
            except OSError:
                continue
    return sorted(set(result))


def root_path(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        fail(f"{label} muss absolut sein")
    return path


def candidate_path(value: str, agent_root: Path) -> Path:
    supplied = root_path(value, "Kandidatenpfad")
    if supplied.is_symlink():
        fail(f"Kandidatenpfad ist ein Symlink: {supplied}")
    try:
        resolved = supplied.resolve(strict=True)
        root = agent_root.resolve(strict=True)
    except OSError as exc:
        fail(f"Kandidatenpfad nicht kanonisch auflösbar: {exc}")
    if resolved.parent != root or not LEGACY_NAME.fullmatch(resolved.name):
        fail(f"Kein exakt historisches Staging unter dem Agent-Root: {supplied}")
    if not resolved.is_dir():
        fail(f"Kandidatenpfad ist kein Verzeichnis: {supplied}")
    return resolved


def active_record(agent_root: Path) -> dict[str, object]:
    active = agent_root / "agent"
    if active.is_symlink() or not active.is_dir():
        fail("Aktiver Agentbaum fehlt oder ist ein Symlink")
    digest, files, symlinks, unsupported = manifest(active)
    if symlinks or unsupported or files == 0:
        fail("Aktiver Agentbaum ist kein verwendbarer Wiederherstellungspfad")
    st = active.stat()
    return {"path": str(active), "manifest_sha256": digest, "file_count": files, "owner": f"{st.st_uid}:{st.st_gid}"}


def inspect(path: Path) -> dict[str, object]:
    digest, files, symlinks, unsupported = manifest(path)
    st = path.stat()
    identity = path / ".release-identity"
    return {
        "path": str(path),
        "name": path.name,
        "manifest_sha256": digest,
        "file_count": files,
        "symlinks": symlinks,
        "unsupported": unsupported,
        "identity_present": identity.exists() or identity.is_symlink(),
        "owner": f"{st.st_uid}:{st.st_gid}",
        "mode": stat.S_IMODE(st.st_mode),
        "mtime_ns": st.st_mtime_ns,
        "process_refs": process_refs(path),
        "systemd_refs": systemd_refs(path),
    }


def assert_record_unchanged(record: dict[str, object], agent_root: Path) -> Path:
    path = candidate_path(str(record["path"]), agent_root)
    current = inspect(path)
    for key in ("name", "manifest_sha256", "file_count", "owner", "mode", "mtime_ns", "identity_present"):
        if current[key] != record[key]:
            fail(f"Kandidat verändert ({key}): {path}")
    if current["identity_present"]:
        fail(f"Historischer Kandidat besitzt unerwartet eine Release-Identität: {path}")
    if current["symlinks"] or current["unsupported"] or current["process_refs"] or current["systemd_refs"]:
        fail(f"Kandidat ist nicht sicher quarantänisierbar: {path}")
    return path


def write_plan(path: Path, payload: dict[str, object]) -> None:
    if path.exists() or path.is_symlink():
        fail(f"Plan existiert bereits; keine Überschreibung: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_audit(path: Path, event: dict[str, object]) -> None:
    encoded = (json.dumps(event, sort_keys=True) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    fd = os.open(path, flags, 0o640)
    try:
        os.write(fd, encoded)
    finally:
        os.close(fd)


def preflight(args: argparse.Namespace) -> None:
    agent_root = root_path(args.agent_root, "Agent-Root")
    state_root = root_path(args.state_root, "State-Root")
    if not agent_root.is_dir() or not state_root.is_dir():
        fail("Agent-Root und State-Root müssen existieren")
    if not args.candidate:
        fail("Mindestens ein expliziter --candidate ist erforderlich")
    paths = [candidate_path(value, agent_root) for value in args.candidate]
    if len({str(path) for path in paths}) != len(paths):
        fail("Kandidatenliste enthält Duplikate")
    global_refs = global_upgrade_refs()
    if global_refs:
        fail(f"Aktiver Upgrade-/Rollback-Prozess gefunden: {global_refs}")
    records = []
    for path in paths:
        record = inspect(path)
        if record["identity_present"]:
            fail(f"Kandidat ist kein Legacy-Staging ohne Identität: {path}")
        if record["symlinks"] or record["unsupported"] or record["process_refs"] or record["systemd_refs"]:
            fail(f"Kandidat nicht freigabefähig: {path}")
        records.append(record)
    payload = {
        "schema": SCHEMA,
        "kind": "legacy-staging-migration",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agent_root": str(agent_root.resolve()),
        "state_root": str(state_root.resolve()),
        "active_restore": active_record(agent_root),
        "candidates": records,
    }
    write_plan(root_path(args.plan_file, "Plan-Datei"), payload)
    print(json.dumps(payload, sort_keys=True, indent=2))


def apply_plan(args: argparse.Namespace) -> None:
    if os.geteuid() != 0:
        fail("Dieser administrative Pfad benötigt root")
    if not args.confirm:
        fail("--apply benötigt --confirm")
    plan_path = root_path(args.plan_file, "Plan-Datei")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Plan nicht lesbar: {exc}")
    if plan.get("schema") != SCHEMA or plan.get("kind") != "legacy-staging-migration":
        fail("Ungültiges Legacy-Migrationsschema")
    agent_root = root_path(args.agent_root, "Agent-Root").resolve(strict=True)
    state_root = root_path(args.state_root, "State-Root").resolve(strict=True)
    if plan.get("agent_root") != str(agent_root) or plan.get("state_root") != str(state_root):
        fail("Plan gehört nicht zu diesem Agent-/State-Root")
    if not isinstance(plan.get("candidates"), list) or not plan["candidates"]:
        fail("Plan enthält keine Kandidaten")
    if active_record(agent_root)["manifest_sha256"] != plan["active_restore"]["manifest_sha256"]:
        fail("Aktiver Wiederherstellungspfad hat sich verändert")
    if global_upgrade_refs():
        fail("Aktiver Upgrade-/Rollback-Prozess gefunden")
    quarantine = root_path(args.quarantine_root, "Quarantänepfad")
    quarantine_parent = quarantine.parent.resolve(strict=True)
    if quarantine_parent != state_root and state_root not in quarantine_parent.parents:
        fail("Quarantänepfad liegt nicht unter dem State-Root")
    if quarantine.exists() and quarantine.is_symlink():
        fail("Quarantänepfad ist ein Symlink")
    quarantine.mkdir(mode=0o750, parents=True, exist_ok=True)
    audit = quarantine / "audit.log"
    if audit.is_symlink():
        fail("Audit-Datei ist ein Symlink")
    for record in plan["candidates"]:
        source = assert_record_unchanged(record, agent_root) if Path(str(record["path"])).exists() else Path(str(record["path"]))
        target = quarantine / str(record["name"])
        target_exists = target.exists() or target.is_symlink()
        if source.exists() and target_exists:
            fail(f"Quelle und Ziel existieren gleichzeitig: {source}")
        if not source.exists():
            if not target.is_dir() or target.is_symlink():
                fail(f"Quelle fehlt und Quarantäneziel ist ungültig: {source}")
            current_digest, current_files, symlinks, unsupported = manifest(target)
            if current_digest != record["manifest_sha256"] or current_files != record["file_count"] or symlinks or unsupported:
                fail(f"Bereits verschobener Kandidat stimmt nicht mit dem Plan überein: {target}")
            append_audit(audit, {"event": "resume_verified", "path": str(source), "target": str(target), "manifest_sha256": current_digest, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            continue
        if target_exists:
            fail(f"Quarantäneziel existiert bereits; keine Überschreibung: {target}")
        try:
            os.rename(source, target)
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                fail("Quarantäne würde ein nicht-atomisches Dateisystem-übergreifendes Verschieben erfordern")
            raise
        digest, files, symlinks, unsupported = manifest(target)
        if digest != record["manifest_sha256"] or files != record["file_count"] or symlinks or unsupported:
            fail(f"Integritätsprüfung nach Quarantäne fehlgeschlagen: {target}")
        append_audit(audit, {"event": "quarantined", "path": str(source), "target": str(target), "manifest_sha256": digest, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print(f"Legacy-Migration abgeschlossen bzw. wiederaufgenommen: {len(plan['candidates'])} Kandidaten")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--candidate", action="append")
    parser.add_argument("--plan-file", required=True)
    parser.add_argument("--agent-root", default="/opt/smart-homelab-maintenance")
    parser.add_argument("--state-root", default="/var/lib/smart-homelab-maintenance")
    parser.add_argument("--quarantine-root", default="/var/lib/smart-homelab-maintenance/staging-quarantine")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.apply:
        apply_plan(args)
    else:
        preflight(args)


if __name__ == "__main__":
    main()
