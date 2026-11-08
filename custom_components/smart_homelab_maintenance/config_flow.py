"""Config flow with HA-independent validation helpers."""

from __future__ import annotations

from typing import Any, Mapping

from .const import CONF_AGENT_URL, CONF_CA_FILE, CONF_POLICY_MODE, CONF_SCAN_INTERVAL, CONF_TOKEN, DEFAULT_SCAN_INTERVAL, MAX_SCAN_INTERVAL, MIN_SCAN_INTERVAL, POLICY_MODES
from .http_transport import AgentHttpTransport, TransportConfig, TransportError, validate_agent_url, validate_ca_file


def validate_config(data: Mapping[str, Any]) -> dict[str, Any]:
    url = validate_agent_url(str(data.get(CONF_AGENT_URL, "")))
    ca_file = validate_ca_file(data.get(CONF_CA_FILE))
    token = str(data.get(CONF_TOKEN, ""))
    interval = int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    if not token or len(token) > 512:
        raise ValueError("token is required")
    if not MIN_SCAN_INTERVAL <= interval <= MAX_SCAN_INTERVAL:
        raise ValueError("scan interval is out of range")
    return {CONF_AGENT_URL: url, CONF_TOKEN: token, CONF_CA_FILE: ca_file, CONF_SCAN_INTERVAL: interval}


try:
    from homeassistant import config_entries
    import voluptuous as vol

    async def _check_agent(data: Mapping[str, Any]) -> None:
        transport = AgentHttpTransport(TransportConfig(data[CONF_AGENT_URL], data[CONF_TOKEN], ca_file=data.get(CONF_CA_FILE)))
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
                    error = {
                        "api_version": "api_version",
                        "authentication": "authentication",
                        "tls_error": "tls_error",
                    }.get(err.code, "cannot_connect")
                    return self.async_show_form(step_id="user", errors={"base": error})
                except ValueError:
                    return self.async_show_form(step_id="user", errors={"base": "invalid_url"})
            return self.async_show_form(step_id="user", data_schema=vol.Schema({
                vol.Required(CONF_AGENT_URL): str,
                vol.Required(CONF_TOKEN): str,
                vol.Optional(CONF_CA_FILE, default=""): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
            }))

        @staticmethod
        def async_get_options_flow(config_entry):
            return SmartHomelabOptionsFlow()

    class SmartHomelabOptionsFlow(config_entries.OptionsFlow):
        async def async_step_init(self, user_input=None):
            if user_input is not None:
                data = {CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
                if CONF_POLICY_MODE in user_input:
                    mode = str(user_input[CONF_POLICY_MODE])
                    if mode not in POLICY_MODES:
                        return self.async_show_form(step_id="init", errors={"base": "invalid_policy_mode"})
                    data[CONF_POLICY_MODE] = mode
                return self.async_create_entry(data=data)
            return self.async_show_form(step_id="init", data_schema=vol.Schema({
                vol.Required(CONF_SCAN_INTERVAL, default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
                vol.Optional(CONF_POLICY_MODE): vol.In(POLICY_MODES),
            }))
except ImportError:
    SmartHomelabConfigFlow = None
    SmartHomelabOptionsFlow = None
