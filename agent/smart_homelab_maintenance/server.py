"""Small HTTPS server for the read-only agent API.

The server is intentionally dependency-free and injectable.  It exposes only
the routes implemented by :class:`ApiApplication`; there is no shell or update
operation endpoint.  A caller must provide certificate/key files and a token
credential explicitly, so an accidental plaintext listener cannot be created.
"""

from __future__ import annotations

import logging
import os
import ssl
import ipaddress
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from .api import ApiApplication
from .security import redact_secrets

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentServerConfig:
    host: str = "127.0.0.1"
    port: int = 48128
    certificate: str | None = None
    private_key: str | None = None
    execution_enabled: bool = False
    max_request_line: int = 4096

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("agent must not bind an unrestricted address")
        try:
            address = ipaddress.ip_address(self.host)
        except ValueError:
            address = None
        if address is not None and address.is_unspecified:
            raise ValueError("agent must not bind an unrestricted address")
        if not 1024 <= self.port <= 65535:
            raise ValueError("agent port must be an unprivileged port")
        if not self.certificate or not self.private_key:
            raise ValueError("TLS certificate and private key are required")
        if self.execution_enabled:
            raise ValueError("update execution is permanently disabled in this phase")


def load_credential(path: str | os.PathLike[str]) -> str:
    """Load and validate a systemd-style credential without logging it."""

    value = Path(path).read_text(encoding="utf-8").strip()
    if not value or len(value) > 512 or any(char.isspace() for char in value):
        raise ValueError("credential is empty or malformed")
    return value


def credential_from_systemd(name: str = "api_token") -> str:
    directory = os.environ.get("CREDENTIALS_DIRECTORY")
    if not directory:
        raise ValueError("CREDENTIALS_DIRECTORY is not set")
    return load_credential(Path(directory) / name)


def tls_context(config: AgentServerConfig) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(config.certificate, config.private_key)
    return context


class AgentRequestHandler(BaseHTTPRequestHandler):
    server_version = "SmartHomelabMaintenanceAgent/0.1"
    sys_version = ""

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        application: ApiApplication = self.server.application  # type: ignore[attr-defined]
        try:
            status, payload = application.handle("GET", self.path, headers=self.headers)
            body = __import__("json").dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            _LOGGER.debug("client disconnected before response was written")
        except Exception as exc:  # do not expose internals to clients
            _LOGGER.warning("agent request failed: %s", redact_secrets(str(exc)))
            try:
                self.send_error(500, "internal server error")
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_POST(self) -> None:  # noqa: N802
        self.send_error(405, "method not allowed")

    def log_message(self, format: str, *args: object) -> None:
        # Access logs must never contain Authorization headers or query tokens.
        _LOGGER.info("agent HTTP request: %s", format.split("%", 1)[0].strip())


class AgentHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, address: tuple[str, int], application: ApiApplication, context: ssl.SSLContext) -> None:
        super().__init__(address, AgentRequestHandler)
        self.application = application
        self.socket = context.wrap_socket(self.socket, server_side=True)


def create_server(application: ApiApplication, config: AgentServerConfig) -> AgentHTTPServer:
    """Create an HTTPS server; it is not started by this function."""

    return AgentHTTPServer((config.host, config.port), application, tls_context(config))


def serve_forever(application: ApiApplication, config: AgentServerConfig, *, server_factory: Callable[..., AgentHTTPServer] = create_server) -> None:
    """Run a caller-supplied application until interrupted, then close it."""

    server = server_factory(application, config)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.shutdown()
        server.server_close()
