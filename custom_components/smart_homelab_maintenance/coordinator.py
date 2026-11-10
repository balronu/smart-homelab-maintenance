"""Async coordinator with bounded polling and exponential error backoff."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Mapping

from .http_transport import AgentHttpTransport, TransportConfig, TransportError
from .compatibility import Compatibility, evaluate_agent

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
    update_error: str | None = None
    compatibility: Compatibility = field(default_factory=lambda: evaluate_agent(None, None))
    orchestration: Mapping[str, Any] | None = None


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
                # Inventory is the primary contract.  Update discovery is an
                # optional Beta.15 extension and must not make valid
                # host/VM/LXC data disappear when its endpoint fails.
                host, virtual_machines, containers, jobs, capabilities = await asyncio.gather(
                    self.transport.host(), self.transport.virtual_machines(), self.transport.containers(),
                    self.transport.jobs(), self.transport.capabilities()
                )
                orchestration_method = getattr(self.transport, "orchestration", None)
                if callable(orchestration_method):
                    try:
                        orchestration = await orchestration_method()
                    except TransportError as exc:
                        orchestration = {"data": {"status": "unavailable", "error": exc.code, "policy_mode": "discover_only"}}
                else:
                    orchestration = {"data": {"status": "unavailable", "policy_mode": "discover_only"}}
                update_error = None
                compatibility = evaluate_agent(None, None)
                try:
                    health_method = getattr(self.transport, "health", None)
                    if not callable(health_method):
                        raise TransportError("health_unavailable", "agent healthcheck is unavailable")
                    health = await health_method()
                    health_data = health.get("data", {})
                    compatibility = evaluate_agent(health_data.get("agent_version"), health_data.get("api_contract"))
                except TransportError as exc:
                    compatibility = evaluate_agent(None, None)
                    update_error = exc.code
                try:
                    updates = await self.transport.updates()
                except TransportError as exc:
                    updates = {"data": {"items": []}}
                    update_error = exc.code
                host_data = host.get("data", {})
                vm_data = virtual_machines.get("data", {})
                cdata = containers.get("data", {})
                jdata = jobs.get("data", {})
                update_items = tuple(updates.get("data", {}).get("items", []))
                update_by_target = {item.get("target"): item for item in update_items}
                execution_enabled = bool((capabilities.get("data") or {}).get("execution_enabled", False))
                active_targets = {job.get("target") for job in jdata.get("items", []) if job.get("state") in {"queued", "preflight", "running", "postcheck", "manual_recovery_required"}}
                update_by_target = {
                    target: dict(item, execution_enabled=execution_enabled, backend_connected=True,
                                 job_conflict=target in active_targets)
                    for target, item in update_by_target.items()
                }
                host_data = dict(host_data, update=update_by_target.get("host"))
                vm_items = [dict(item, update=update_by_target.get(f"vm:{item.get('vmid')}")) for item in vm_data.get("items", [])]
                container_items = [dict(item, update=update_by_target.get(f"container:{item.get('container_id')}")) for item in cdata.get("items", [])]
                dry_runs = dict(self._dry_runs)
                host_data["update"] = dict(host_data.get("update") or {}, dry_run=dry_runs.get("host")) if host_data.get("update") else None
                container_items = [dict(item, update=dict(item.get("update") or {}, dry_run=dry_runs.get(f"container:{item.get('container_id')}")) if item.get("update") else None) for item in container_items]
                vm_items = [dict(item, update=dict(item.get("update") or {}, dry_run=dry_runs.get(f"vm:{item.get('vmid')}")) if item.get("update") else None) for item in vm_items]
                self.data = CoordinatorData(
                    connected=True,
                    host=host_data,
                    virtual_machines=tuple(vm_items),
                    containers=tuple(container_items),
                    jobs=tuple(jdata.get("items", [])),
                    capabilities=capabilities.get("data"),
                    updates=update_items,
                    dry_runs=dry_runs,
                    update_error=update_error,
                    compatibility=compatibility,
                    orchestration=orchestration,
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
        inventory_manager = getattr(self, "_inventory_entity_manager", None)
        if inventory_manager is not None:
            inventory_manager.stop()
            self._inventory_entity_manager = None
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None

    @property
    def backoff_seconds(self) -> int:
        return min(self.update_interval * (2 ** min(self._failure_count, 5)), 3600)
