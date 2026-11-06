"""Async HTTP client for the versioned Smart Homelab Maintenance agent API.

This copy is deliberately part of the Home Assistant integration package. A
normal HA installation loads only ``custom_components/<domain>`` and must not
depend on the separate agent source tree being installed beside it.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class TransportError(Exception):
    """A sanitized, structured transport or API error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class TransportConfig:
    """Bounded configuration for the read-only agent transport."""

    base_url: str
    token: str
    timeout_seconds: float = 5.0
    max_response_bytes: int = 256_000
    api_version: str = "1"

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("offline transport accepts localhost endpoints only")
        if not self.token or len(self.token) > 512:
            raise ValueError("token is required and bounded")
        if not 0.1 <= self.timeout_seconds <= 30:
            raise ValueError("timeout must be between 0.1 and 30 seconds")


class AgentHttpTransport:
    """Read-only client for the versioned agent API."""

    def __init__(self, config: TransportConfig) -> None:
        self.config = config

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
        except (ConnectionError, OSError, urllib.error.URLError) as exc:
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
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(self.config.max_response_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise TransportError("http_error", "agent returned an HTTP error") from exc
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
            raise TransportError(str(error.get("code", "agent_error")), "agent request failed")
        return result

    async def health(self) -> dict[str, Any]:
        return await self.get("/api/v1/health")

    async def containers(self) -> dict[str, Any]:
        return await self.get("/api/v1/containers?limit=100")

    async def capabilities(self) -> dict[str, Any]:
        return await self.get("/api/v1/capabilities")

    async def jobs(self) -> dict[str, Any]:
        return await self.get("/api/v1/jobs?limit=100")

    async def job(self, job_id: str) -> dict[str, Any]:
        return await self.get("/api/v1/jobs/" + job_id)

    async def job_events(self, job_id: str, after: int = 0) -> dict[str, Any]:
        return await self.get(f"/api/v1/jobs/{job_id}/events?after={after}&limit=50")
