"""Binary sensor projections for connection and update blocks."""

from __future__ import annotations

from typing import Any, Mapping


def binary_values(data: Any) -> tuple[dict[str, Any], ...]:
    return ({"unique_id": "agent_connected", "name": "Agent erreichbar", "is_on": bool(data.connected)},)


try:
    from homeassistant.components.binary_sensor import BinarySensorEntity
    from homeassistant.helpers.entity import DeviceInfo
    from .const import DOMAIN

    class _ConnectionBinarySensor(BinarySensorEntity):
        _attr_name = "Agent reachable"
        _attr_unique_id = "agent_connected"
        _attr_should_poll = False
        def __init__(self, coordinator): self.coordinator = coordinator
        @property
        def is_on(self): return bool(self.coordinator.data.connected)
        @property
        def device_info(self): return DeviceInfo(identifiers={(DOMAIN, "agent")}, name="Smart Homelab Maintenance")
        async def async_added_to_hass(self):
            self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    async def async_setup_entry(hass, entry, async_add_entities):
        async_add_entities([_ConnectionBinarySensor(hass.data[DOMAIN][entry.entry_id])])
except ImportError:
    BinarySensorEntity = object
