"""Secret-free diagnostics."""

from __future__ import annotations


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data["smart_homelab_maintenance"].get(entry.entry_id)
    return {"connected": bool(coordinator and coordinator.data.connected), "last_error": getattr(coordinator, "last_error", None), "execution_enabled": False}
