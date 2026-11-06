from __future__ import annotations

import json
import ssl
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TLS_SCRIPT = ROOT / "scripts" / "tls-agent.sh"


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        body = json.dumps({"schema_version": "1", "data": {"status": "ok"}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


class SelfSignedTlsTests(unittest.TestCase):
    def _issue(self, output: Path, ip: str, prefix: str = "agent") -> None:
        result = subprocess.run(
            [
                str(TLS_SCRIPT),
                "self-signed",
                "--output-dir",
                str(output),
                "--ip",
                ip,
                "--prefix",
                prefix,
                "--apply",
                "--confirm",
            ],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_self_signed_certificate_has_ip_san_and_safe_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            agent_ip = ".".join(("192", "168", "178", "199"))
            self._issue(output, agent_ip)
            check = subprocess.run(
                ["openssl", "x509", "-in", str(output / "agent.crt"), "-noout", "-checkip", agent_ip],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertEqual((output / "agent.key").stat().st_mode & 0o777, 0o600)
            self.assertEqual((output / "agent.crt").stat().st_mode & 0o777, 0o644)

    def test_real_https_accepts_explicit_trust_and_rejects_missing_or_wrong_trust(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            self._issue(output, "127.0.0.1")
            self._issue(output, "127.0.0.2", "wrong")

            server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthHandler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(output / "agent.crt", output / "agent.key")
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"https://127.0.0.1:{server.server_port}/api/v1/health"
            try:
                trusted = ssl.create_default_context(cafile=output / "agent.crt")
                with urllib.request.urlopen(url, context=trusted, timeout=3) as response:
                    self.assertEqual(json.loads(response.read())["data"]["status"], "ok")

                with self.assertRaises((urllib.error.URLError, ssl.SSLError)):
                    with urllib.request.urlopen(url, context=ssl.create_default_context(), timeout=3):
                        pass

                wrong_trust = ssl.create_default_context(cafile=output / "wrong.crt")
                with self.assertRaises((urllib.error.URLError, ssl.SSLError)):
                    with urllib.request.urlopen(url, context=wrong_trust, timeout=3):
                        pass
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_reissue_requires_distinct_output_name_and_keeps_confirmation_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            blocked = subprocess.run(
                [str(TLS_SCRIPT), "self-signed", "--output-dir", str(output), "--ip", "127.0.0.1"],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("--apply und --confirm", blocked.stderr)
            self._issue(output, "127.0.0.1")
            self._issue(output, "127.0.0.1", "renewed")


if __name__ == "__main__":
    unittest.main()
