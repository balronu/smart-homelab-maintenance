"""Read-only update entity projection; execution is intentionally unavailable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class UpdateValue:
    unique_id: str
    installed_version: str | None
    available_version: str | None
    supported: bool
    blocked_reasons: tuple[str, ...]
    update_execution_enabled: bool = False

    @property
    def has_update(self) -> bool:
        return bool(self.supported and self.installed_version and self.available_version and self.installed_version != self.available_version)


def update_value(app: dict[str, Any]) -> UpdateValue:
    return UpdateValue(f"app_{app['app_id']}", app.get("installed_version"), app.get("available_version"), bool(app.get("update_supported")), tuple(app.get("blocked_reasons", ())))


try:
    from homeassistant.components.update import UpdateEntity
    from homeassistant.helpers.entity import DeviceInfo
    from .const import DOMAIN

    class _ReadOnlyUpdate(UpdateEntity):
        _attr_should_poll = False
        _attr_supported_features = set()
        def __init__(self, coordinator, app):
            self.coordinator, self.app_id = coordinator, str(app.get("app_id"))
            self._attr_unique_id = f"app_{self.app_id}"
            self._attr_name = str(app.get("name", self.app_id))
        def _app(self):
            for container in self.coordinator.data.containers:
                for app in container.get("applications", container.get("apps", [])):
                    if str(app.get("app_id")) == self.app_id: return app
            return {}
        @property
        def installed_version(self): return self._app().get("installed_version")
        @property
        def latest_version(self): return self._app().get("available_version")
        @property
        def available(self): return bool(self._app())
        @property
        def in_progress(self): return False
        @property
        def device_info(self): return DeviceInfo(identifiers={(DOMAIN, "agent")}, name="Smart Homelab Maintenance")
        async def async_added_to_hass(self):
            self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    async def async_setup_entry(hass, entry, async_add_entities):
        coordinator = hass.data[DOMAIN][entry.entry_id]
        apps = []
        for container in coordinator.data.containers:
            apps.extend(container.get("applications", container.get("apps", [])))
        async_add_entities([_ReadOnlyUpdate(coordinator, app) for app in apps if app.get("update_supported") and not app.get("blocked_reasons")])
except ImportError:
    UpdateEntity = object
