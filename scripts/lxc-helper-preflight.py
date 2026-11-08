#!/usr/bin/env python3
"""Read-only, machine-readable preflight for the LXC helper installer."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Sequence

REQUIRED_FILES = (
    "agent/smart_homelab_maintenance/server.py",
    "custom_components/smart_homelab_maintenance/manifest.json",
    "deploy/systemd/smart-homelab-maintenance-agent.service.example",
    "scripts/smh-lxc-apt-helper.py",
    "scripts/smart-homelab-maintenance-lxc-helper.service",
    "scripts/smh-lxc-discovery.py",
    "scripts/smart-homelab-maintenance-lxc-discovery.service",
)
TARGETS = (
    Path("/usr/libexec/smart-homelab-maintenance/lxc-apt-helper"),
    Path("/usr/libexec/smart-homelab-maintenance/lxc-discovery.py"),
    Path("/etc/systemd/system/smart-homelab-maintenance-lxc-helper.service"),
    Path("/etc/systemd/system/smart-homelab-maintenance-lxc-discovery.service"),
    Path("/etc/smart-homelab-maintenance/lxc-apt-allowlist.toml"),
)


def check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def command(argv: Sequence[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, **kwargs)


def preflight(source_dir: Path, expected_commit: str, *, runner=command) -> dict[str, object]:
    checks: list[dict[str, str]] = []
    if os.geteuid() != 0:
        checks.append(check("root", "FAIL", "root is required for installation"))
    else:
        checks.append(check("root", "PASS", "running as root"))

    if not source_dir.is_dir() or source_dir.resolve() == Path("/"):
        checks.append(check("source", "FAIL", "source directory is missing or unsafe"))
    else:
        checks.append(check("source", "PASS", "source directory exists"))

    if len(expected_commit) != 40 or any(c not in "0123456789abcdef" for c in expected_commit):
        checks.append(check("expected_commit", "FAIL", "expected commit must be a 40-character SHA-1"))
    else:
        result = runner(["git", "-C", str(source_dir), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False)
        actual = result.stdout.strip()
        checks.append(check("source_commit", "PASS" if result.returncode == 0 and actual == expected_commit else "FAIL", "exact source commit verified" if actual == expected_commit else "source commit mismatch"))
        clean = runner(["git", "-C", str(source_dir), "diff", "--quiet"], capture_output=True, text=True, timeout=5, check=False)
        checks.append(check("source_clean", "PASS" if clean.returncode == 0 else "FAIL", "source worktree is clean" if clean.returncode == 0 else "source worktree has changes"))

    missing = [str(source_dir / item) for item in REQUIRED_FILES if not (source_dir / item).is_file()]
    checks.append(check("required_files", "PASS" if not missing else "FAIL", "all installer inputs exist" if not missing else "missing: " + ", ".join(missing)))

    unsafe = []
    for path in TARGETS:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            unsafe.append(str(path))
        if path.name == "lxc-apt-allowlist.toml" and path.exists():
            stat = path.stat()
            if stat.st_uid != 0 or stat.st_mode & 0o777 not in {0o600, 0o640, 0o644}:
                unsafe.append(f"{path} (owner/mode)")
    checks.append(check("target_safety", "PASS" if not unsafe else "FAIL", "target paths are safe or absent" if not unsafe else "unsafe: " + ", ".join(unsafe)))

    systemctl = runner(["systemctl", "is-system-running"], capture_output=True, text=True, timeout=5, check=False)
    state = systemctl.stdout.strip() or "unavailable"
    checks.append(check("systemd", "PASS" if state in {"running", "degraded"} else "FAIL", f"systemd state: {state}"))

    failed = [item["name"] for item in checks if item["status"] == "FAIL"]
    return {
        "schema_version": "1",
        "decision": "NO-GO" if failed else "GO",
        "apply_authorization_required": True,
        "mutations_performed": False,
        "failed_checks": failed,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    result = preflight(args.source_dir, args.expected_commit)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["decision"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
