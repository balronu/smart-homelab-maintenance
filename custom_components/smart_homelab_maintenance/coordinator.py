"""Async coordinator with bounded polling and exponential error backoff."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Mapping

from .http_transport import AgentHttpTransport, TransportConfig, TransportError

from .const import CONF_AGENT_URL, CONF_CA_FILE, CONF_SCAN_INTERVAL, CONF_TOKEN, DEFAULT_SCAN_INTERVAL, MAX_SCAN_INTERVAL, MIN_SCAN_INTERVAL


@dataclass(frozen=True, slots=True)
class CoordinatorData:
    connected: bool
    host: Mapping[str, Any] | None = None
    virtual_machines: tuple[Mapping[str, Any], ...] = ()
    containers: tuple[Mapping[str, Any], ...] = ()
    jobs: tuple[Mapping[str, Any], ...] = ()
    capabilities: Mapping[str, Any] | None = None
    updates: tuple[Mapping[str, Any], ...] = ()
    dry_runs: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
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
        self._unsub_interval = None
        self._dry_runs: dict[str, Mapping[str, Any]] = {}

    async def async_config_entry_first_refresh(self) -> None:
        await self.async_update()

    async def async_update(self) -> CoordinatorData:
        if self._lock.locked():
            return self.data
        async with self._lock:
            try:
                host, virtual_machines, containers, jobs, capabilities, updates = await asyncio.gather(
                    self.transport.host(), self.transport.virtual_machines(), self.transport.containers(),
                    self.transport.jobs(), self.transport.capabilities(), self.transport.updates()
                )
                host_data = host.get("data", {})
                vm_data = virtual_machines.get("data", {})
                cdata = containers.get("data", {})
                jdata = jobs.get("data", {})
                update_items = tuple(updates.get("data", {}).get("items", []))
                update_by_target = {item.get("target"): item for item in update_items}
                host_data = dict(host_data, update=update_by_target.get("host"))
                vm_items = [dict(item, update=update_by_target.get(f"vm:{item.get('vmid')}")) for item in vm_data.get("items", [])]
                container_items = [dict(item, update=update_by_target.get(f"container:{item.get('container_id')}")) for item in cdata.get("items", [])]
                dry_runs = dict(self._dry_runs)
                host_data["update"] = dict(host_data.get("update") or {}, dry_run=dry_runs.get("host")) if host_data.get("update") else None
                container_items = [dict(item, update=dict(item.get("update") or {}, dry_run=dry_runs.get(f"container:{item.get('container_id')}")) if item.get("update") else None) for item in container_items]
                vm_items = [dict(item, update=dict(item.get("update") or {}, dry_run=dry_runs.get(f"vm:{item.get('vmid')}")) if item.get("update") else None) for item in vm_items]
                self.data = CoordinatorData(
                    True, host_data, tuple(vm_items), tuple(container_items),
                    tuple(jdata.get("items", [])), capabilities.get("data"), update_items, dry_runs, None
                )
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

    def record_dry_run(self, target: str, result: Mapping[str, Any]) -> None:
        self._dry_runs[target] = dict(result)

    def async_add_listener(self, update_callback):
        """Small listener bridge; returns an unsubscribe callback."""
        self._listeners = getattr(self, "_listeners", [])
        self._listeners.append(update_callback)
        return lambda: self._listeners.remove(update_callback) if update_callback in self._listeners else None

    def set_unsub_interval(self, unsubscribe) -> None:
        self._unsub_interval = unsubscribe

    def async_stop(self) -> None:
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None

    @property
    def backoff_seconds(self) -> int:
        return min(self.update_interval * (2 ** min(self._failure_count, 5)), 3600)
