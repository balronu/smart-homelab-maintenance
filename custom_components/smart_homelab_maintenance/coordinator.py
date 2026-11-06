"""Async coordinator with bounded polling and exponential error backoff."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Mapping

from .http_transport import AgentHttpTransport, TransportConfig, TransportError

from .const import CONF_AGENT_URL, CONF_CA_FILE, CONF_SCAN_INTERVAL, CONF_TOKEN, DEFAULT_SCAN_INTERVAL, MAX_SCAN_INTERVAL, MIN_SCAN_INTERVAL


@dataclass(frozen=True, slots=True)
class CoordinatorData:
    connected: bool
    containers: tuple[Mapping[str, Any], ...] = ()
    jobs: tuple[Mapping[str, Any], ...] = ()
    capabilities: Mapping[str, Any] | None = None
    error: str | None = None


class SmartHomelabCoordinator:
    def __init__(self, hass: Any, data: Mapping[str, Any], options: Mapping[str, Any] | None = None) -> None:
        self.hass = hass
        options = options or {}
        interval = int(options.get(CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))
        self.update_interval = max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, interval))
        self.transport = AgentHttpTransport(TransportConfig(str(data[CONF_AGENT_URL]), str(data[CONF_TOKEN]), ca_file=data.get(CONF_CA_FILE)))
        self.data = CoordinatorData(False)
        self.last_error: str | None = None
        self._lock = asyncio.Lock()
        self._failure_count = 0

    async def async_config_entry_first_refresh(self) -> None:
        await self.async_update()

    async def async_update(self) -> CoordinatorData:
        if self._lock.locked():
            return self.data
        async with self._lock:
            try:
                containers, jobs, capabilities = await asyncio.gather(self.transport.containers(), self.transport.jobs(), self.transport.capabilities())
                cdata = containers.get("data", {})
                jdata = jobs.get("data", {})
                self.data = CoordinatorData(True, tuple(cdata.get("items", [])), tuple(jdata.get("items", [])), capabilities.get("data"), None)
                self.last_error = None
                self._failure_count = 0
            except TransportError as exc:
                self._failure_count += 1
                self.last_error = exc.code
                self.data = CoordinatorData(False, error=exc.code)
            for callback in getattr(self, "_listeners", []):
                callback()
            return self.data

    async def async_request_refresh(self) -> CoordinatorData:
        """HA-compatible refresh hook used by tests and future polling."""
        return await self.async_update()

    def async_add_listener(self, update_callback):
        """Small listener bridge; returns an unsubscribe callback."""
        self._listeners = getattr(self, "_listeners", [])
        self._listeners.append(update_callback)
        return lambda: self._listeners.remove(update_callback) if update_callback in self._listeners else None
    @property
    def backoff_seconds(self) -> int:
        return min(self.update_interval * (2 ** min(self._failure_count, 5)), 3600)
