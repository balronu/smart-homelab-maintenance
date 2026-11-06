"""Config flow with HA-independent validation helpers."""

from __future__ import annotations

from typing import Any, Mapping

from .const import CONF_AGENT_URL, CONF_SCAN_INTERVAL, CONF_TOKEN, DEFAULT_SCAN_INTERVAL, MAX_SCAN_INTERVAL, MIN_SCAN_INTERVAL
from agent.smart_homelab_maintenance.http_transport import AgentHttpTransport, TransportConfig, TransportError


def validate_config(data: Mapping[str, Any]) -> dict[str, Any]:
    url = str(data.get(CONF_AGENT_URL, "")).rstrip("/")
    token = str(data.get(CONF_TOKEN, ""))
    interval = int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    if not (url.startswith("http://127.0.0.1") or url.startswith("http://localhost")):
        raise ValueError("agent_url must point to localhost in this offline phase")
    if not token or len(token) > 512:
        raise ValueError("token is required")
    if not MIN_SCAN_INTERVAL <= interval <= MAX_SCAN_INTERVAL:
        raise ValueError("scan interval is out of range")
    return {CONF_AGENT_URL: url, CONF_TOKEN: token, CONF_SCAN_INTERVAL: interval}


try:
    from homeassistant import config_entries
    import voluptuous as vol

    async def _check_agent(data: Mapping[str, Any]) -> None:
        transport = AgentHttpTransport(TransportConfig(data[CONF_AGENT_URL], data[CONF_TOKEN]))
        await transport.health()
        await transport.capabilities()

    class SmartHomelabConfigFlow(config_entries.ConfigFlow, domain="smart_homelab_maintenance"):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            if user_input is not None:
                try:
                    clean = validate_config(user_input)
                    await _check_agent(clean)
                    await self.async_set_unique_id(clean[CONF_AGENT_URL].lower())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=clean[CONF_AGENT_URL], data=clean)
                except TransportError as err:
                    error = "api_version" if err.code == "api_version" else "cannot_connect"
                    return self.async_show_form(step_id="user", errors={"base": error})
                except (TypeError, ValueError):
                    return self.async_show_form(step_id="user", errors={"base": "cannot_connect"})
            return self.async_show_form(step_id="user", data_schema=vol.Schema({
                vol.Required(CONF_AGENT_URL): str,
                vol.Required(CONF_TOKEN): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
            }))

        @staticmethod
        def async_get_options_flow(config_entry):
            return SmartHomelabOptionsFlow()

    class SmartHomelabOptionsFlow(config_entries.OptionsFlow):
        async def async_step_init(self, user_input=None):
            if user_input is not None:
                return self.async_create_entry(data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])})
            return self.async_show_form(step_id="init", data_schema=vol.Schema({
                vol.Required(CONF_SCAN_INTERVAL, default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
            }))
except ImportError:
    SmartHomelabConfigFlow = None
    SmartHomelabOptionsFlow = None
