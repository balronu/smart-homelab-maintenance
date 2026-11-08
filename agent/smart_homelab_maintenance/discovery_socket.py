"""Root-owned, fixed-scope discovery socket contract.

The server validates peer credentials and request shape, but receives its
probe callback by dependency injection. No guest command runner is wired into
this module; production deployment must provide a separately reviewed fixed
probe implementation.
"""

from __future__ import annotations

import json
import os
import pwd
import socket
import socketserver
import struct
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .discovery_transport import DISCOVERY_OPERATION, DISCOVERY_SOCKET, build_request, validate_response

MAX_REQUEST_BYTES = 16 * 1024
EXPECTED_CLIENT_USER = "smart-homelab-maintenance"


class DiscoverySocketError(ValueError):
    """A bounded, structured discovery socket error."""


def verify_peer_uid(sock: socket.socket, *, expected_uid: int | None = None) -> None:
    try:
        uid, _, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if expected_uid is None:
            expected_uid = pwd.getpwnam(EXPECTED_CLIENT_USER).pw_uid
    except (OSError, KeyError, struct.error) as exc:
        raise DiscoverySocketError("unauthorized_client") from exc
    if uid != expected_uid:
        raise DiscoverySocketError("unauthorized_client")


def validate_discovery_request(payload: Any) -> int:
    if not isinstance(payload, Mapping) or set(payload) != {"container_id", "operation"}:
        raise DiscoverySocketError("invalid_request")
    if payload.get("operation") != DISCOVERY_OPERATION:
        raise DiscoverySocketError("operation_not_allowed")
    try:
        return build_request(payload["container_id"]).container_id
    except (KeyError, ValueError) as exc:
        raise DiscoverySocketError("invalid_container") from exc


class FixedDiscoveryServer:
    """Single-request server with peer, size, timeout and concurrency gates."""

    def __init__(self, socket_path: str = DISCOVERY_SOCKET, *, probe: Callable[[int], Mapping[str, Any]], expected_uid: int | None = None, require_root: bool = True) -> None:
        if socket_path != DISCOVERY_SOCKET:
            raise DiscoverySocketError("socket_path_invalid")
        if require_root and os.geteuid() != 0:
            raise DiscoverySocketError("root_required")
        self.socket_path = socket_path
        self.probe = probe
        self.expected_uid = expected_uid
        self._lock = threading.Lock()

    def response(self, payload: Any, *, peer_socket: socket.socket | None = None) -> dict[str, Any]:
        try:
            if peer_socket is not None:
                verify_peer_uid(peer_socket, expected_uid=self.expected_uid)
            container_id = validate_discovery_request(payload)
            with self._lock:
                result = validate_response(
                    {"ok": True, "container_id": container_id, "operation": DISCOVERY_OPERATION, "result": self.probe(container_id)},
                    container_id=container_id,
                )
            return {"ok": True, "container_id": container_id, "operation": DISCOVERY_OPERATION, "result": result}
        except DiscoverySocketError as exc:
            return {"ok": False, "error": {"code": str(exc)}}
        except (OSError, TimeoutError, TypeError, ValueError):
            return {"ok": False, "error": {"code": "probe_failed"}}

    def serve_forever(self) -> None:
        if os.geteuid() != 0:
            raise DiscoverySocketError("root_required")
        path = Path(self.socket_path)
        path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        if path.exists():
            raise DiscoverySocketError("socket_already_exists")
        owner = _DiscoveryRequestHandler
        owner.service = self
        with socketserver.ThreadingUnixStreamServer(self.socket_path, owner) as server:
            server.daemon_threads = False
            os.chmod(self.socket_path, 0o660)
            server.serve_forever()


class _DiscoveryRequestHandler(socketserver.StreamRequestHandler):
    service: FixedDiscoveryServer

    def handle(self) -> None:
        self.request.settimeout(10)
        try:
            line = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if len(line) > MAX_REQUEST_BYTES or not line.endswith(b"\n"):
                raise DiscoverySocketError("request_limit")
            payload = json.loads(line.decode("utf-8"))
            result = self.service.response(payload, peer_socket=self.request)
        except (UnicodeDecodeError, json.JSONDecodeError):
            result = {"ok": False, "error": {"code": "invalid_request"}}
        except (OSError, DiscoverySocketError):
            result = {"ok": False, "error": {"code": "request_failed"}}
        self.wfile.write((json.dumps(result, separators=(",", ":")) + "\n").encode("utf-8"))
