"""Sensor descriptions and HA-independent entity value projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class SensorValue:
    unique_id: str
    name: str
    value: Any
    attributes: Mapping[str, Any]


def coordinator_sensors(data: Any) -> tuple[SensorValue, ...]:
    return (
        SensorValue("agent_connection", "Agent-Verbindung", "connected" if data.connected else "offline", {"error": data.error, "update_error": data.update_error}),
        SensorValue("agent_running_jobs", "Laufende Jobs", len([j for j in data.jobs if j.get("state") in {"queued", "preflight", "running", "verifying", "postcheck", "interrupted", "recovery_pending", "recovery_blocked", "manual_recovery_required"}]), {"jobs": _job_summaries(data.jobs), "lifecycle_states": {state: sum(1 for j in data.jobs if j.get("state") == state) for state in sorted({j.get("state") for j in data.jobs})}}),
        SensorValue("agent_last_error", "Letzter Fehler", data.error or data.update_error or "none", {}),
        SensorValue("agent_compatibility", "Agent-Kompatibilität", data.compatibility.status, data.compatibility.as_attributes()),
        SensorValue("agent_helper_status", "LXC-Helper-Status", _helper_status(data.orchestration), _orchestration_attributes(data.orchestration)),
    )


def _orchestration_data(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    data = value.get("data")
    return data if isinstance(data, Mapping) else value


def _helper_status(value: Mapping[str, Any] | None) -> str:
    data = _orchestration_data(value)
    if data.get("helper_installed") is True and data.get("discovery_socket_active") is True and data.get("integrity_ok") is True:
        return "ready"
    return "not_installed" if data.get("helper_installed") is False else "unavailable"


def _orchestration_attributes(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(_orchestration_data(value))


def _job_summaries(jobs: Any) -> list[dict[str, Any]]:
    fields = ("job_id", "target", "state", "phase", "progress", "message", "error_code", "error_message", "created_at", "started_at", "finished_at")
    return [{key: job.get(key) for key in fields if key in job} for job in jobs if isinstance(job, Mapping)]


def container_sensors(container: Mapping[str, Any]) -> tuple[SensorValue, ...]:
    cid = container["container_id"]
    return (SensorValue(f"container_{cid}_status", str(container["name"]), "running" if container.get("running") else "stopped", {"os": container.get("os_name")} ),)


try:
    from homeassistant.components.sensor import SensorEntity
    from homeassistant.helpers.entity import DeviceInfo
    from .const import DOMAIN

    class _ProjectedSensor(SensorEntity):
        _attr_should_poll = False
        def __init__(self, coordinator, unique_id, name, value_fn, attributes_fn=None, device_id="agent"):
            self.coordinator, self._value_fn, self._attributes_fn = coordinator, value_fn, attributes_fn
            self._attr_unique_id, self._attr_name = unique_id, name
            self._device_id = device_id
        @property
        def native_value(self): return self._value_fn(self.coordinator.data)
        @property
        def extra_state_attributes(self): return (self._attributes_fn(self.coordinator.data) if self._attributes_fn else {})
        @property
        def device_info(self): return DeviceInfo(identifiers={(DOMAIN, self._device_id)}, name="Smart Homelab Maintenance")
        async def async_added_to_hass(self):
            self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    class _ContainerSensor(_ProjectedSensor):
        pass

    class _InventoryEntityManager:
        """Keep per-guest entities aligned with late inventory discovery.

        The first coordinator refresh happens before Home Assistant forwards
        platform setup.  If that refresh fails, the old implementation created
        no VM/LXC entities and never retried entity creation after a later
        successful poll.  The card intentionally reads those entities, so the
        inventory remained visually empty while the coordinator had valid
        API data.
        """

        def __init__(self, coordinator, async_add_entities):
            self.coordinator = coordinator
            self._async_add_entities = async_add_entities
            self._known: set[str] = set()
            self._unsubscribe = coordinator.async_add_listener(self._on_update)

        def _entities_for_current_data(self):
            entities = []
            data = self.coordinator.data
            for vm in data.virtual_machines:
                vmid = str(vm.get("vmid"))
                unique_id = f"vm_{vmid}"
                if unique_id in self._known:
                    continue
                self._known.add(unique_id)
                entities.append(_ProjectedSensor(
                    self.coordinator, unique_id, str(vm.get("name", vmid)),
                    lambda d, vmid=vmid: next(("running" if item.get("running") else "stopped" for item in d.virtual_machines if str(item.get("vmid")) == vmid), "unknown"),
                    lambda d, vmid=vmid: next((dict(item) for item in d.virtual_machines if str(item.get("vmid")) == vmid), {}),
                    f"vm_{vmid}",
                ))
            for container in data.containers:
                cid = str(container.get("container_id"))
                unique_id = f"container_{cid}_status"
                if unique_id in self._known:
                    continue
                self._known.add(unique_id)
                entities.append(_ContainerSensor(
                    self.coordinator, unique_id, str(container.get("name", cid)),
                    lambda d, cid=cid: next(("running" if item.get("running") else "stopped" for item in d.containers if str(item.get("container_id")) == cid), "unknown"),
                    lambda d, cid=cid: next((dict(item) for item in d.containers if str(item.get("container_id")) == cid), {}),
                    f"container_{cid}",
                ))
            return entities

        def initial_entities(self):
            return self._entities_for_current_data()

        def _on_update(self):
            new_entities = self._entities_for_current_data()
            if new_entities:
                self._async_add_entities(new_entities)

        def stop(self):
            if self._unsubscribe:
                self._unsubscribe()
                self._unsubscribe = None

    async def async_setup_entry(hass, entry, async_add_entities):
        coordinator = hass.data["smart_homelab_maintenance"][entry.entry_id]
        inventory = _InventoryEntityManager(coordinator, async_add_entities)
        coordinator._inventory_entity_manager = inventory
        entities = [
            _ProjectedSensor(coordinator, "agent_connection", "Agent connection", lambda d: "connected" if d.connected else "offline", lambda d: {"error": d.error}),
            _ProjectedSensor(coordinator, "agent_running_jobs", "Running jobs", lambda d: len([j for j in d.jobs if j.get("state") in {"queued", "preflight", "running", "verifying", "postcheck", "interrupted", "recovery_pending", "recovery_blocked", "manual_recovery_required"}]), lambda d: {"jobs": _job_summaries(d.jobs), "lifecycle_states": {state: sum(1 for j in d.jobs if j.get("state") == state) for state in sorted({j.get("state") for j in d.jobs})}, "last_recovery_at": max((j.get("last_recovery_at") or "" for j in d.jobs), default=None), "recovery_reasons": [j.get("message") for j in d.jobs if j.get("state") in {"recovery_pending", "recovery_blocked", "manual_recovery_required"} and j.get("message")] } ),
            _ProjectedSensor(coordinator, "agent_last_error", "Last error", lambda d: d.error or "none"),
            _ProjectedSensor(coordinator, "agent_compatibility", "Agent compatibility", lambda d: d.compatibility.status, lambda d: d.compatibility.as_attributes()),
            _ProjectedSensor(coordinator, "agent_helper_status", "LXC helper status", lambda d: _helper_status(d.orchestration), lambda d: _orchestration_attributes(d.orchestration)),
            _ProjectedSensor(coordinator, "host", "Host", lambda d: d.host.get("name", "unknown") if d.host else "unknown", lambda d: d.host or {}),
        ]
        entities.extend(inventory.initial_entities())
        async_add_entities(entities)
except ImportError:
    SensorEntity = object
