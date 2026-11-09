"""Async HTTP client for the versioned Smart Homelab Maintenance agent API.

This copy is deliberately part of the Home Assistant integration package. A
normal HA installation loads only ``custom_components/<domain>`` and must not
depend on the separate agent source tree being installed beside it.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit


PRIVATE_DNS_SUFFIXES = (".home.arpa", ".lan", ".local")


def validate_ca_file(value: str | None) -> str | None:
    """Allow only an explicit CA file in HA's persistent SSL directory."""

    raw = str(value or "").strip()
    if not raw:
        return None
    if ".." in raw.split("/"):
        raise ValueError("ca_file must not contain path traversal")
    path = PurePosixPath(raw)
    if not path.is_absolute() or path.parts[:2] != ("/", "ssl"):
        raise ValueError("ca_file must be an absolute path below /ssl")
    if ".." in path.parts or path.suffix.lower() not in {".pem", ".crt", ".cer"}:
        raise ValueError("ca_file must be a certificate file below /ssl")
    return str(path)


def validate_agent_url(value: str) -> str:
    """Return a normalized private HTTPS URL or reject it fail-closed."""

    raw = str(value).strip().rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("agent_url must use HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("agent_url must not contain credentials or query data")
    hostname = parsed.hostname.lower()
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if hostname != "localhost" and not hostname.endswith(PRIVATE_DNS_SUFFIXES):
            raise ValueError("agent_url must use a private DNS suffix")
    else:
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ValueError("agent_url must use a private address")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("agent_url has an invalid port") from exc
    authority = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None:
        authority += f":{port}"
    return f"https://{authority}"


class TransportError(Exception):
    """A sanitized, structured transport or API error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_SAFE_AGENT_MESSAGES = {
    "target is not a proven Debian/Ubuntu apt LXC",
    "only running LXC targets may be authorized",
    "target eligibility could not be verified",
    "target eligibility probe is unavailable",
    "container is not authorized",
    "container is not in the root-owned allowlist",
    "privileged policy helper is unavailable",
}


def _safe_agent_error(exc: urllib.error.HTTPError, *, fallback_code: str = "http_error") -> TransportError:
    """Expose only bounded, explicitly safe API validation messages to HA."""
    try:
        raw = exc.read(8193)
        payload = json.loads(raw.decode("utf-8"))
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message") if isinstance(error, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        message = None
        code = None
    if not isinstance(message, str) or message not in _SAFE_AGENT_MESSAGES:
        message = "agent rejected the request" if 400 <= exc.code < 500 else "agent request failed"
    safe_code = str(code) if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,48}", code) else fallback_code
    if exc.code in {401, 403}:
        safe_code = "authentication"
        message = "agent authentication failed"
    return TransportError(safe_code, message)


@dataclass(frozen=True, slots=True)
class TransportConfig:
    """Bounded configuration for the read-only agent transport."""

    base_url: str
    token: str
    timeout_seconds: float = 5.0
    max_response_bytes: int = 256_000
    api_version: str = "1"
    ca_file: str | None = None

    def __post_init__(self) -> None:
        validate_agent_url(self.base_url)
        validate_ca_file(self.ca_file)
        if not self.token or len(self.token) > 512:
            raise ValueError("token is required and bounded")
        if not 0.1 <= self.timeout_seconds <= 30:
            raise ValueError("timeout must be between 0.1 and 30 seconds")


class AgentHttpTransport:
    """Read-only client for the versioned agent API."""

    def __init__(self, config: TransportConfig) -> None:
        self.config = config

    def _ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(cafile=self.config.ca_file)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return context

    async def get(self, path: str) -> dict[str, Any]:
        if not path.startswith("/api/v1/"):
            raise TransportError("invalid_path", "only API v1 paths are allowed")
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._get_sync, path),
                self.config.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise TransportError("timeout", "agent request timed out") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                raise TransportError("tls_error", "agent TLS verification failed") from exc
            raise TransportError("connection", "agent connection failed") from exc
        except (ConnectionError, OSError) as exc:
            raise TransportError("connection", "agent connection failed") from exc

    def _get_sync(self, path: str) -> dict[str, Any]:
        request = urllib.request.Request(
            self.config.base_url.rstrip("/") + path,
            headers={
                "Authorization": "Bearer " + self.config.token,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout_seconds,
                context=self._ssl_context(),
            ) as response:
                raw = response.read(self.config.max_response_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise _safe_agent_error(exc) from exc
        if len(raw) > self.config.max_response_bytes:
            raise TransportError("response_too_large", "agent response exceeds limit")
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError("invalid_json", "agent returned invalid JSON") from exc
        if not isinstance(result, dict) or result.get("schema_version") != self.config.api_version:
            raise TransportError("api_version", "unsupported agent API version")
        if "error" in result:
            error = result["error"]
            message = error.get("message") if isinstance(error, dict) else None
            if message not in _SAFE_AGENT_MESSAGES:
                message = "agent request failed"
            raise TransportError(str(error.get("code", "agent_error")), message)
        return result

    async def health(self) -> dict[str, Any]:
        return await self.get("/api/v1/health")

    async def containers(self) -> dict[str, Any]:
        return await self.get("/api/v1/containers?limit=100")

    async def host(self) -> dict[str, Any]:
        return await self.get("/api/v1/host")

    async def virtual_machines(self) -> dict[str, Any]:
        return await self.get("/api/v1/virtual-machines?limit=100")

    async def updates(self) -> dict[str, Any]:
        return await self.get("/api/v1/updates")

    async def dry_run(self, target: str) -> dict[str, Any]:
        if not isinstance(target, str) or not re.fullmatch(r"(?:host|container:[1-9][0-9]{0,5})", target):
            raise TransportError("invalid_target", "update target is not allowed")
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._post_json_sync, f"/api/v1/updates/{target}/dry-run", {"confirm": True}),
                self.config.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise TransportError("timeout", "agent request timed out") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                raise TransportError("tls_error", "agent TLS verification failed") from exc
            raise TransportError("connection", "agent connection failed") from exc
        except (ConnectionError, OSError) as exc:
            raise TransportError("connection", "agent connection failed") from exc

    async def execute_update(self, target: str, *, plan_digest: str | None) -> dict[str, Any]:
        if not isinstance(target, str) or not re.fullmatch(r"container:[1-9][0-9]{0,5}", target):
            raise TransportError("invalid_target", "only numeric LXC targets may be updated")
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._post_json_sync, f"/api/v1/updates/{target}/execute", {"confirm": True, "plan_digest": plan_digest}),
                self.config.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise TransportError("timeout", "agent request timed out") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                raise TransportError("tls_error", "agent TLS verification failed") from exc
            raise TransportError("connection", "agent connection failed") from exc

    async def set_permissions(self, target: str, *, simulation_authorized: bool, update_authorized: bool) -> dict[str, Any]:
        if not isinstance(target, str) or not re.fullmatch(r"container:[1-9][0-9]{0,5}", target):
            raise TransportError("invalid_target", "only numeric LXC targets may be authorized")
        payload = {"confirm": True, "simulation_authorized": bool(simulation_authorized), "update_authorized": bool(update_authorized)}
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._post_json_sync, f"/api/v1/updates/{target}/permissions", payload),
                self.config.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise TransportError("timeout", "agent request timed out") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                raise TransportError("tls_error", "agent TLS verification failed") from exc
            raise TransportError("connection", "agent connection failed") from exc
        except (ConnectionError, OSError) as exc:
            raise TransportError("connection", "agent connection failed") from exc
        except (ConnectionError, OSError) as exc:
            raise TransportError("connection", "agent connection failed") from exc

    def _post_json_sync(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.config.base_url.rstrip("/") + path,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={"Authorization": "Bearer " + self.config.token, "Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds, context=self._ssl_context()) as response:
                raw = response.read(self.config.max_response_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise _safe_agent_error(exc) from exc
        if len(raw) > self.config.max_response_bytes:
            raise TransportError("response_too_large", "agent response exceeds limit")
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError("invalid_json", "agent returned invalid JSON") from exc
        if not isinstance(result, dict) or result.get("schema_version") != self.config.api_version:
            raise TransportError("api_version", "unsupported agent API version")
        if "error" in result:
            error = result["error"]
            message = error.get("message") if isinstance(error, dict) else None
            if message not in _SAFE_AGENT_MESSAGES:
                message = "agent request failed"
            raise TransportError(str(error.get("code", "agent_error")), message)
        return result


    async def capabilities(self) -> dict[str, Any]:
        return await self.get("/api/v1/capabilities")

    async def orchestration(self) -> dict[str, Any]:
        return await self.get("/api/v1/orchestration")

    async def policy(self) -> dict[str, Any]:
        return await self.get("/api/v1/policy")

    async def policy_prepare(self, *, mode: str, generation: int, manual_authorized_ids: list[int] | None = None) -> dict[str, Any]:
        return await self._post_json("/api/v1/policy/prepare", {"mode": mode, "generation": generation, "manual_authorized_ids": manual_authorized_ids or []})

    async def policy_apply(self, *, mode: str, generation: int, confirm: bool, manual_authorized_ids: list[int] | None = None) -> dict[str, Any]:
        return await self._post_json("/api/v1/policy/apply", {"mode": mode, "generation": generation, "confirm": bool(confirm), "manual_authorized_ids": manual_authorized_ids or []})

    async def orchestration_preview(self) -> dict[str, Any]:
        return await self._post_json("/api/v1/orchestration/preview", {})

    async def orchestration_apply(self, *, preview_token: str, confirm: bool) -> dict[str, Any]:
        return await self._post_json("/api/v1/orchestration/apply", {"preview_token": preview_token, "confirm": bool(confirm)})

    async def jobs(self) -> dict[str, Any]:
        return await self.get("/api/v1/jobs?limit=100")

    async def job(self, job_id: str) -> dict[str, Any]:
        return await self.get("/api/v1/jobs/" + job_id)

    async def job_events(self, job_id: str, after: int = 0) -> dict[str, Any]:
        return await self.get(f"/api/v1/jobs/{job_id}/events?after={after}&limit=50")

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._post_json_sync, path, payload), self.config.timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise TransportError("timeout", "agent request timed out") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                raise TransportError("tls_error", "agent TLS verification failed") from exc
            raise TransportError("connection", "agent connection failed") from exc
        except (ConnectionError, OSError) as exc:
            raise TransportError("connection", "agent connection failed") from exc
