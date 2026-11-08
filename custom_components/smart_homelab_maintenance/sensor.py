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
        SensorValue("agent_running_jobs", "Laufende Jobs", len([j for j in data.jobs if j.get("state") in {"preflight", "running", "postcheck"}]), {}),
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

    async def async_setup_entry(hass, entry, async_add_entities):
        coordinator = hass.data["smart_homelab_maintenance"][entry.entry_id]
        entities = [
            _ProjectedSensor(coordinator, "agent_connection", "Agent connection", lambda d: "connected" if d.connected else "offline", lambda d: {"error": d.error}),
            _ProjectedSensor(coordinator, "agent_running_jobs", "Running jobs", lambda d: len([j for j in d.jobs if j.get("state") in {"preflight", "running", "postcheck"}])),
            _ProjectedSensor(coordinator, "agent_last_error", "Last error", lambda d: d.error or "none"),
            _ProjectedSensor(coordinator, "agent_compatibility", "Agent compatibility", lambda d: d.compatibility.status, lambda d: d.compatibility.as_attributes()),
            _ProjectedSensor(coordinator, "agent_helper_status", "LXC helper status", lambda d: _helper_status(d.orchestration), lambda d: _orchestration_attributes(d.orchestration)),
            _ProjectedSensor(coordinator, "host", "Host", lambda d: d.host.get("name", "unknown") if d.host else "unknown", lambda d: d.host or {}),
        ]
        for vm in coordinator.data.virtual_machines:
            vmid = str(vm.get("vmid"))
            entities.append(_ProjectedSensor(
                coordinator, f"vm_{vmid}", str(vm.get("name", vmid)),
                lambda d, vmid=vmid: next(("running" if item.get("running") else "stopped" for item in d.virtual_machines if str(item.get("vmid")) == vmid), "unknown"),
                lambda d, vmid=vmid: next((dict(item) for item in d.virtual_machines if str(item.get("vmid")) == vmid), {}),
                f"vm_{vmid}"
            ))
        for container in coordinator.data.containers:
            cid = str(container.get("container_id"))
            entities.append(_ContainerSensor(coordinator, f"container_{cid}_status", str(container.get("name", cid)), lambda d, cid=cid: next(("running" if c.get("running") else "stopped" for c in d.containers if str(c.get("container_id")) == cid), "unknown"), lambda d, cid=cid: next((dict(c) for c in d.containers if str(c.get("container_id")) == cid), {}), f"container_{cid}"))
        async_add_entities(entities)
except ImportError:
    SensorEntity = object
