#!/usr/bin/env python3
"""Exercise the fixed helper protocol against a disposable guest fixture.

This is deliberately not a Proxmox test guest.  It proves that the exact
helper request validation, status gate, fixed pct argv, update lock, two-step
execution and real dpkg mutation compose correctly without touching the host
package database or network.  A real non-production LXC remains a separate
acceptance requirement.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts" / "smh-lxc-apt-helper.py"
spec = importlib.util.spec_from_file_location("smh_lxc_apt_helper_fixture", HELPER_PATH)
assert spec and spec.loader
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def run() -> None:
    if shutil.which("dpkg") is None or shutil.which("dpkg-deb") is None:
        raise SystemExit("SKIP: dpkg and dpkg-deb are required")
    with tempfile.TemporaryDirectory(prefix="smh-helper-guest-") as temp:
        guest = Path(temp) / "guest"
        work = Path(temp) / "work"
        (guest / "var/lib/dpkg").mkdir(parents=True)
        (work / "pkg/DEBIAN").mkdir(parents=True)
        (work / "pkg/usr/share/smh-e2e").mkdir(parents=True)
        (guest / "var/lib/dpkg/status").touch()

        def package(version: str, marker: str) -> Path:
            control = work / "pkg/DEBIAN/control"
            control.write_text(
                "Package: smh-helper-guest-fixture\n"
                f"Version: {version}\nArchitecture: all\n"
                "Maintainer: Smart Homelab Maintenance\n"
                "Description: disposable helper transport fixture\n",
                encoding="utf-8",
            )
            (work / "pkg/usr/share/smh-e2e/version").write_text(marker + "\n", encoding="utf-8")
            output = work / f"fixture-{version}.deb"
            subprocess.run(["dpkg-deb", "--build", str(work / "pkg"), str(output)], check=True, stdout=subprocess.DEVNULL)
            return output

        first = package("1.0", "fixture-v1")
        subprocess.run(["dpkg", f"--root={guest}", f"--admindir={guest / 'var/lib/dpkg'}", f"--instdir={guest}", "-i", str(first)], check=True, stdout=subprocess.DEVNULL)
        second = package("2.0", "fixture-v2")
        calls: list[list[str]] = []

        def transport(argv: list[str], **_kwargs):
            calls.append(argv)
            if argv[1] == "status":
                return 0, "status: running\n", ""
            assert argv[:5] == ["/usr/sbin/pct", "exec", "321", "--", "/usr/bin/apt-get"]
            if argv[5] == "update":
                return 0, "fixture index unchanged\n", ""
            assert argv[5:] == ["--yes", "--no-remove", "upgrade"]
            completed = subprocess.run(
                ["dpkg", f"--root={guest}", f"--admindir={guest / 'var/lib/dpkg'}", f"--instdir={guest}", "-i", str(second)],
                capture_output=True,
                text=True,
                check=False,
            )
            return completed.returncode, completed.stdout, completed.stderr

        result = helper.handle(
            {"container_id": 321, "operation": "update"},
            allowed_ids={321},
            update_ids={321},
            run=transport,
        )
        if not result.get("ok") or [step["name"] for step in result["steps"]] != ["apt-update", "apt-upgrade"]:
            raise AssertionError(result)
        if calls != [
            ["/usr/sbin/pct", "status", "321"],
            ["/usr/sbin/pct", "exec", "321", "--", "/usr/bin/apt-get", "update"],
            ["/usr/sbin/pct", "exec", "321", "--", "/usr/bin/apt-get", "--yes", "--no-remove", "upgrade"],
        ]:
            raise AssertionError(calls)
        query = subprocess.run(
            ["dpkg-query", f"--root={guest}", f"--admindir={guest / 'var/lib/dpkg'}", "-W", "-f=${Version}\n", "smh-helper-guest-fixture"],
            capture_output=True,
            text=True,
            check=True,
        )
        if query.stdout.strip() != "2.0":
            raise AssertionError(query.stdout)
        if (guest / "usr/share/smh-e2e/version").read_text(encoding="utf-8").strip() != "fixture-v2":
            raise AssertionError("guest marker was not upgraded")
        print("PASS: fixed helper protocol reached disposable guest fixture and performed real dpkg upgrade")
        print("NOT RUN: real Proxmox LXC transport; no designated non-production test guest was available")


if __name__ == "__main__":
    run()
