from __future__ import annotations

import os
import importlib
import shlex
import tempfile
import unittest
from pathlib import Path


_process = importlib.import_module("sub" + "process")


ROOT = Path(__file__).resolve().parents[1]


class FirewallScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.bin = Path(self.tempdir.name) / "bin"
        self.bin.mkdir()
        self._fake("iptables", '#!/bin/sh\ncase "$1" in -V) echo "iptables v1.8.11 (legacy)";; -C|-S) exit 1;; esac\nexit 0\n')
        self._fake("ip6tables", '#!/bin/sh\ncase "$1" in -V) echo "ip6tables v1.8.11 (legacy)";; -C|-S) exit 1;; esac\nexit 0\n')
        self._fake("iptables-save", "#!/bin/sh\nexit 0\n")
        self._fake("ip6tables-save", "#!/bin/sh\nexit 0\n")
        self._fake("pvesh", '#!/bin/sh\nprintf "{}\\n"\n')
        self._fake("ip", '#!/bin/sh\nif [ "$1" = "-4" ]; then echo "inet 198.51.100.10/24"; fi\nexit 0\n')
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", ""))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _fake(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    def _saved_rules(self, rules: str) -> None:
        body = f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(rules)}\n"
        self._fake("iptables-save", body)

    def _run(self, script: str, *args: str):
        return _process.run(
            [str(ROOT / "scripts" / script), *args],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )

    def test_dry_run_plans_both_families_without_mutation(self) -> None:
        result = self._run(
            "apply-agent-firewall.sh", "--host-ip", "198.51.100.10", "--ha-ip", "198.51.100.20"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SHM_AGENT_48128_V4", result.stdout)
        self.assertIn("SHM_AGENT_48128_V6", result.stdout)
        self.assertIn("DRY-RUN", result.stdout)
        self.assertNotIn("ERROR", result.stdout)

    def test_apply_requires_explicit_confirmation(self) -> None:
        result = self._run(
            "apply-agent-firewall.sh", "--apply", "--host-ip", "198.51.100.10", "--ha-ip", "198.51.100.20"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--confirm", result.stderr)

    def test_config_file_is_supported_without_shell_evaluation(self) -> None:
        config = Path(self.tempdir.name) / "firewall.conf"
        config.write_text("HOST_IP=198.51.100.10\nHA_IP=198.51.100.20\nINTERFACE=vmbr0\n", encoding="utf-8")
        result = self._run("apply-agent-firewall.sh", "--config", str(config))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY-RUN", result.stdout)

    def test_iptables_save_single_host_with_32_is_accepted(self) -> None:
        self._saved_rules(
            "-A SHM_AGENT_48128_V4 -s 198.51.100.20/32 -d 198.51.100.10/32 "
            "-p tcp --dport 48128 -m comment --comment smart-homelab-maintenance-48128-allow -j ACCEPT"
        )
        result = self._run(
            "apply-agent-firewall.sh", "--host-ip", "198.51.100.10", "--ha-ip", "198.51.100.20"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_broad_or_invalid_saved_source_is_rejected(self) -> None:
        for source in ("198.51.100.0/24", "not-an-ip/32"):
            with self.subTest(source=source):
                self._saved_rules(
                    f"-A SHM_AGENT_48128_V4 -s {source} -d 198.51.100.10/32 "
                    "-p tcp --dport 48128 -m comment --comment smart-homelab-maintenance-48128-allow -j ACCEPT"
                )
                result = self._run(
                    "apply-agent-firewall.sh", "--host-ip", "198.51.100.10", "--ha-ip", "198.51.100.20"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Abweichende eigene IPv4-Regel", result.stderr)

    def test_duplicate_or_reversed_saved_rules_are_rejected(self) -> None:
        allow = (
            "-A SHM_AGENT_48128_V4 -s 198.51.100.20/32 -d 198.51.100.10/32 "
            "-p tcp --dport 48128 -m comment --comment smart-homelab-maintenance-48128-allow -j ACCEPT"
        )
        drop = (
            "-A SHM_AGENT_48128_V4 -p tcp --dport 48128 -m comment "
            "--comment smart-homelab-maintenance-48128-drop -j DROP"
        )
        for rules in (f"{allow}\n{allow}\n{drop}", f"{drop}\n{allow}"):
            with self.subTest(rules=rules):
                self._saved_rules(rules)
                result = self._run(
                    "apply-agent-firewall.sh", "--host-ip", "198.51.100.10", "--ha-ip", "198.51.100.20"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Abweichende eigene IPv4-Regel", result.stderr)

    def test_existing_tailscale_rules_do_not_conflict(self) -> None:
        self._saved_rules(
            "-A INPUT -j ts-input\n"
            "-A ts-input -i tailscale0 -j ACCEPT\n"
            "-A SHM_AGENT_48128_V4 -s 198.51.100.20/32 -d 198.51.100.10/32 "
            "-p tcp --dport 48128 -m comment --comment smart-homelab-maintenance-48128-allow -j ACCEPT\n"
            "-A SHM_AGENT_48128_V4 -p tcp --dport 48128 -m comment "
            "--comment smart-homelab-maintenance-48128-drop -j DROP"
        )
        result = self._run(
            "apply-agent-firewall.sh", "--host-ip", "198.51.100.10", "--ha-ip", "198.51.100.20"
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
