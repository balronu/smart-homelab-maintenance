"""Home Assistant adapter boundary.

The domain logic stays in ``agent.smart_homelab_maintenance``. This module
only coordinates transport data and never exposes update execution.
"""

from __future__ import annotations

from .const import ACTIONS, DOMAIN

PLATFORMS = ("sensor", "binary_sensor", "update")

try:  # Home Assistant is optional for offline tests.
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, SupportsResponse
    from homeassistant.helpers import config_validation as cv
    import voluptuous as vol
except ImportError:  # pragma: no cover - exercised by the offline environment
    ConfigEntry = object  # type: ignore[misc,assignment]
    HomeAssistant = object  # type: ignore[misc,assignment]
    SupportsResponse = None
    cv = None
    vol = None

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN) if cv else None


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the domain without starting any update execution."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["actions"] = ACTIONS
    if vol is not None:
        async def handle_action(call):
            entry_id = call.data.get("entry_id")
            coordinator = hass.data[DOMAIN].get(entry_id) if entry_id else next(
                (value for key, value in hass.data[DOMAIN].items() if key != "actions"), None
            )
            if coordinator is None:
                return {"error": "not_configured"}
            from .actions import async_action
            result = await async_action(
                coordinator.transport,
                call.service,
                job_id=call.data.get("job_id"),
                cursor=int(call.data.get("after", 0)),
            )
            hass.data[DOMAIN].setdefault("last_action_result", {})[call.service] = result
            return result

        schema = vol.Schema({
            vol.Optional("entry_id"): str,
            vol.Optional("job_id"): str,
            vol.Optional("after", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=1000000)),
        })
        for action in ("check", "get_job", "get_job_events"):
            kwargs = {"schema": schema}
            if SupportsResponse is not None:
                kwargs["supports_response"] = SupportsResponse.ONLY
            hass.services.async_register(DOMAIN, action, handle_action, **kwargs)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    from .coordinator import SmartHomelabCoordinator
    coordinator = SmartHomelabCoordinator(hass, entry.data, entry.options)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded
