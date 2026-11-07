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
import argparse
import json
import re
import signal
import threading
import tomllib
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .api import ApiApplication
from .discovery import DiscoveryService
from .jobs import JobRepository
from .proxmox_backend import ProxmoxApiClient, ProxmoxClientConfig, ProxmoxInventoryBackend
from .updates import AptCommandRunner, AptUpdateReader, RootHelperTransport, UpdateService, make_targets
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


@dataclass(frozen=True, slots=True)
class AgentRuntimeConfig:
    server: AgentServerConfig
    state_directory: str
    proxmox: ProxmoxClientConfig
    max_response_bytes: int = 256_000
    update_targets: dict[str, dict[str, Any]] = field(default_factory=dict)
    lxc_helper_enabled: bool = False


def _strict_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def load_runtime_config(path: str | os.PathLike[str]) -> AgentRuntimeConfig:
    """Load non-secret runtime settings from a TOML file."""

    try:
        with Path(path).open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("agent configuration could not be loaded") from exc
    try:
        server = AgentServerConfig(
            host=str(raw["listen_host"]), port=int(raw["listen_port"]),
            certificate=str(raw["certificate"]), private_key=str(raw["private_key"]),
            execution_enabled=_strict_bool(raw.get("execution_enabled", False), "execution_enabled"),
        )
        proxmox = ProxmoxClientConfig(
            base_url=str(raw["proxmox_url"]), node=str(raw["proxmox_node"]),
            api_token="configuration-credential-placeholder",
            ca_file=str(raw["proxmox_ca_file"]) if raw.get("proxmox_ca_file") else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("agent configuration is invalid") from exc
    state_directory = str(raw.get("state_directory", ""))
    if not state_directory or not Path(state_directory).is_absolute():
        raise ValueError("state_directory must be an absolute path")
    max_bytes = int(raw.get("max_response_bytes", 256_000))
    if max_bytes < 1024:
        raise ValueError("max_response_bytes is too small")
    raw_targets = raw.get("update_targets", {})
    if not isinstance(raw_targets, dict):
        raise ValueError("update_targets must be a TOML table")
    update_targets: dict[str, dict[str, Any]] = {}
    for target, values in raw_targets.items():
        if not isinstance(target, str) or not isinstance(values, dict):
            raise ValueError("update_targets entries are invalid")
        if not re.fullmatch(r"(?:host|container:[1-9][0-9]{0,5}|vm:[1-9][0-9]{0,5})", target):
            raise ValueError("update target is not allowed")
        allowed = {"authorized", "os_name", "os_version", "package_manager"}
        if set(values) - allowed:
            raise ValueError("update target contains unsupported fields")
        if "authorized" in values and not isinstance(values["authorized"], bool):
            raise ValueError("update target authorization must be boolean")
        if any(key in values and not isinstance(values[key], str) for key in {"os_name", "os_version", "package_manager"}):
            raise ValueError("update target metadata must be strings")
        update_targets[target] = dict(values)
    helper_enabled = _strict_bool(raw.get("lxc_helper_enabled", False), "lxc_helper_enabled")
    return AgentRuntimeConfig(server, state_directory, proxmox, max_bytes, update_targets, helper_enabled)


def build_application(config: AgentRuntimeConfig, *, agent_token: str, proxmox_token: str) -> tuple[ApiApplication, JobRepository]:
    """Construct the live read-only application from validated settings."""

    if not agent_token or not proxmox_token:
        raise ValueError("required credentials are missing")
    proxmox_config = ProxmoxClientConfig(
        base_url=config.proxmox.base_url, node=config.proxmox.node,
        api_token=proxmox_token, ca_file=config.proxmox.ca_file,
        timeout=config.proxmox.timeout, max_bytes=config.proxmox.max_bytes,
    )
    repository = JobRepository(str(Path(config.state_directory) / "jobs.sqlite"))
    backend = ProxmoxInventoryBackend(ProxmoxApiClient(proxmox_config))
    discovery = DiscoveryService(backend)
    guest_transport = RootHelperTransport() if config.lxc_helper_enabled else None
    updates = UpdateService(
        lambda: make_targets(discovery.host(), [item.as_dict() for item in discovery.containers()], config.update_targets, discovery.virtual_machines()),
        runner=AptCommandRunner(guest_transport=guest_transport),
        reader=AptUpdateReader(guest_transport=guest_transport),
    )
    application = ApiApplication(discovery, repository, updates=updates,
                                read_token=agent_token, max_bytes=config.max_response_bytes)
    return application, repository


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
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
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
        application: ApiApplication = self.server.application  # type: ignore[attr-defined]
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 16_384:
                self.send_error(413, "request body too large")
                return
            body = self.rfile.read(length)
            status, payload = application.handle("POST", self.path, headers=self.headers, body=body)
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            _LOGGER.debug("client disconnected before response was written")
        except Exception as exc:
            _LOGGER.warning("agent POST request failed: %s", redact_secrets(str(exc)))
            try:
                self.send_error(500, "internal server error")
            except (BrokenPipeError, ConnectionResetError):
                pass

    def log_message(self, format: str, *args: object) -> None:
        # Access logs must never contain Authorization headers or query tokens.
        _LOGGER.info("agent HTTP request: %s", format.split("%", 1)[0].strip())


class AgentHTTPServer(ThreadingHTTPServer):
    # Permit a new listener after the previous process closed its socket. This
    # does not permit two live listeners; SO_REUSEPORT is not enabled.
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], application: ApiApplication, context: ssl.SSLContext) -> None:
        super().__init__(address, AgentRequestHandler)
        self.application = application
        self.socket = context.wrap_socket(self.socket, server_side=True)


def create_server(application: ApiApplication, config: AgentServerConfig) -> AgentHTTPServer:
    """Create an HTTPS server; it is not started by this function."""

    return AgentHTTPServer((config.host, config.port), application, tls_context(config))


def serve_forever(application: ApiApplication, config: AgentServerConfig, *, server_factory: Callable[..., AgentHTTPServer] = create_server) -> None:
    """Run the application with bounded, signal-safe socket shutdown."""

    server = server_factory(application, config)
    previous_handlers: dict[int, Any] = {}

    def request_shutdown(signum: int, _frame: Any) -> None:
        _LOGGER.info("agent shutdown requested by signal %s", signum)
        # BaseServer.shutdown() must run from another thread than
        # serve_forever(); doing so lets the loop leave cleanly and makes the
        # finally block close the listening socket before systemd restarts us.
        threading.Thread(target=server.shutdown, name="agent-shutdown", daemon=True).start()

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            try:
                previous_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, request_shutdown)
            except (ValueError, RuntimeError):
                # Injectable test servers may run outside the main thread.
                pass
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smart Homelab Maintenance read-only agent")
    parser.add_argument("--config", default=os.environ.get("SMART_HOMELAB_AGENT_CONFIG"))
    args = parser.parse_args(argv)
    if not args.config:
        parser.error("--config or SMART_HOMELAB_AGENT_CONFIG is required")
    try:
        config = load_runtime_config(args.config)
        agent_token = credential_from_systemd("api_token")
        proxmox_token = credential_from_systemd("proxmox_api_token")
        application, repository = build_application(config, agent_token=agent_token, proxmox_token=proxmox_token)
        try:
            serve_forever(application, config.server)
        finally:
            repository.close()
    except (OSError, ValueError) as exc:
        _LOGGER.error("agent startup failed: %s", redact_secrets(str(exc)))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
