"""Isolated Home Assistant 2026.11 runtime checks for the integration."""

from __future__ import annotations

import pytest
import pytest_asyncio
import socket
import sys

from homeassistant import auth, loader
from homeassistant.components import http
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.config_entries import ConfigEntries, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import frame

from custom_components.smart_homelab_maintenance.http_transport import AgentHttpTransport, TransportError
from custom_components.smart_homelab_maintenance.const import CARD_VERSION, DOMAIN

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        http_port = probe.getsockname()[1]
    loader.async_setup(instance)
    frame.async_setup(instance)
    instance.config_entries = ConfigEntries(instance, {"components": {}})
    await instance.config_entries.async_initialize()
    # HA 2026.2 removed the public module-level setup helper in favor of the
    # singleton accessor; newer HA releases expose async_setup again. Keep the
    # fixture compatible with both the local HA runtime and the CI pin.
    if hasattr(dr, "async_setup"):
        dr.async_setup(instance)
    else:
        dr.async_get(instance)
    instance.auth = await auth.auth_manager_from_config(instance, [], [])
    await http.async_setup(instance, {"http": {"server_port": http_port}})
    instance.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda _action, _url: None, [])
    await dr.async_load(instance)
    await er.async_load(instance)
    await instance.async_start()
    yield instance
    await instance.async_stop()


def _payloads():
    containers = {"schema_version": "1", "data": {"items": [{
        "container_id": 102, "name": "zigbee2mqtt", "running": True,
        "os_name": "Debian", "os_version": "12", "applications": [{
            "app_id": "zigbee2mqtt_home", "name": "Zigbee2MQTT",
            "installed_version": "2.14.2", "available_version": "2.14.3",
            "update_supported": True, "blocked_reasons": [],
        }],
    }]}}
    return ({"schema_version": "1", "data": {"name": "pve-home", "online": True, "cpu_percent": 12.5}},
            {"schema_version": "1", "data": {"items": [{"vmid": 104, "name": "haos", "status": "running"}]}},
            containers, {"schema_version": "1", "data": {"items": []}},
            {"schema_version": "1", "data": {"execution_enabled": False}},
            {"schema_version": "1", "data": {"status": "ok"}})


@pytest.fixture
def patched_transport(monkeypatch):
    host, virtual_machines, containers, jobs, capabilities, health = _payloads()
    updates = {"schema_version": "1", "data": {"items": []}}
    orchestration = {"schema_version": "1", "data": {"status": "unavailable", "policy_mode": "discover_only", "helper_installed": False, "discovery_socket_active": False, "integrity_ok": False}}

    async def fake_host(self): return host
    async def fake_virtual_machines(self): return virtual_machines
    async def fake_containers(self): return containers
    async def fake_jobs(self): return jobs
    async def fake_capabilities(self): return capabilities
    async def fake_updates(self): return updates
    async def fake_health(self): return health
    async def fake_orchestration(self): return orchestration
    async def fake_dry_run(self, target):
        return {"schema_version": "1", "data": {"target": target, "status": "simulated", "packages": []}}

    monkeypatch.setattr(AgentHttpTransport, "host", fake_host)
    monkeypatch.setattr(AgentHttpTransport, "virtual_machines", fake_virtual_machines)
    monkeypatch.setattr(AgentHttpTransport, "containers", fake_containers)
    monkeypatch.setattr(AgentHttpTransport, "jobs", fake_jobs)
    monkeypatch.setattr(AgentHttpTransport, "capabilities", fake_capabilities)
    monkeypatch.setattr(AgentHttpTransport, "updates", fake_updates)
    monkeypatch.setattr(AgentHttpTransport, "health", fake_health)
    monkeypatch.setattr(AgentHttpTransport, "orchestration", fake_orchestration)
    monkeypatch.setattr(AgentHttpTransport, "dry_run", fake_dry_run)


async def _create_entry(hass: HomeAssistant, token="fixture-token"):
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    return await hass.config_entries.flow.async_configure(flow["flow_id"], {
        "agent_url": "https://agent.home.arpa:8765", "token": token, "scan_interval": 30,
    })


async def test_config_flow_creates_entry_rejects_duplicate_and_options(hass, patched_transport):
    result = await _create_entry(hass)
    assert result["type"] == "create_entry"
    entry = result["result"]
    assert entry.unique_id == "https://agent.home.arpa:8765"
    duplicate = await _create_entry(hass, "another-token")
    assert duplicate["type"] == "abort"
    assert duplicate["reason"] == "already_configured"
    options = await hass.config_entries.options.async_init(entry.entry_id)
    options = await hass.config_entries.options.async_configure(options["flow_id"], {"scan_interval": 60})
    assert options["type"] == "create_entry"
    assert options["data"] == {"scan_interval": 60}


async def test_config_flow_reports_connection_and_api_errors(hass, monkeypatch):
    async def unavailable(self):
        raise TransportError("connection", "offline fixture")
    monkeypatch.setattr(AgentHttpTransport, "health", unavailable)
    result = await _create_entry(hass)
    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"
    async def incompatible(self):
        raise TransportError("api_version", "wrong schema")
    monkeypatch.setattr(AgentHttpTransport, "health", incompatible)
    result = await _create_entry(hass)
    assert result["type"] == "form"
    assert result["errors"]["base"] == "api_version"


async def test_integration_package_has_no_agent_tree_runtime_dependency(hass, monkeypatch):
    """The HA package must load when only custom_components is installed."""

    class BlockAgentImports:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "agent" or fullname.startswith("agent."):
                raise ModuleNotFoundError("agent package intentionally unavailable")
            return None

    blocker = BlockAgentImports()
    sys.meta_path.insert(0, blocker)
    try:
        from custom_components.smart_homelab_maintenance import actions, config_flow, coordinator

        assert config_flow.SmartHomelabConfigFlow is not None
        assert coordinator.AgentHttpTransport is AgentHttpTransport
        assert actions.AgentHttpTransport is AgentHttpTransport
    finally:
        sys.meta_path.remove(blocker)


async def test_setup_registers_entities_devices_services_and_survives_reload(hass, patched_transport):
    from custom_components import smart_homelab_maintenance as integration
    assert await integration.async_setup(hass, {})
    assert hass.data[DOMAIN]["card_registered"] is True
    assert f"/smart_homelab_maintenance/smart-homelab-maintenance-card.js?v={CARD_VERSION}" in hass.data[DATA_EXTRA_MODULE_URL].urls
    result = await _create_entry(hass)
    entry = result["result"]
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    unique_ids = {item.unique_id for item in entities}
    assert {"agent_connection", "agent_running_jobs", "agent_last_error", "host", "vm_104", "container_102_status"} <= unique_ids
    devices = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(devices, entry.entry_id)
    assert any((DOMAIN, "agent") in device.identifiers for device in device_entries)
    assert all(hass.services.has_service(DOMAIN, action) for action in ("check", "get_job", "get_job_events"))
    assert not hass.services.has_service(DOMAIN, "preflight")
    assert all("fixture-token" not in str(item) for item in entities)
    before = set(unique_ids)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    after = {item.unique_id for item in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert after == before


async def test_inventory_entities_are_added_after_initial_inventory_failure(hass, monkeypatch):
    """A recovered poll must materialize the entities consumed by the card."""
    from custom_components import smart_homelab_maintenance as integration

    phase = {"value": 0}
    vms = [{"vmid": 100 + index, "name": f"vm-{index}", "running": True} for index in range(2)]
    containers = [{"container_id": 200 + index, "name": f"lxc-{index}", "running": True} for index in range(10)]

    async def inventory(self, items):
        if not phase["value"]:
            raise TransportError("connection", "agent temporarily unavailable")
        return {"schema_version": "1", "data": {"items": items}}

    async def fake_host(self): return {"schema_version": "1", "data": {"name": "pve-home", "online": True}}
    async def fake_vms(self): return await inventory(self, vms)
    async def fake_containers(self): return await inventory(self, containers)
    async def fake_jobs(self): return {"schema_version": "1", "data": {"items": []}}
    async def fake_capabilities(self): return {"schema_version": "1", "data": {"execution_enabled": False}}
    async def fake_updates(self): return {"schema_version": "1", "data": {"items": []}}
    async def fake_health(self): return {"schema_version": "1", "data": {"agent_version": "0.1.0-beta.47", "api_contract": "1.1"}}
    async def fake_orchestration(self): return {"schema_version": "1", "data": {"status": "ok", "helper_installed": True, "discovery_socket_active": True, "integrity_ok": True}}

    monkeypatch.setattr(AgentHttpTransport, "host", fake_host)
    monkeypatch.setattr(AgentHttpTransport, "virtual_machines", fake_vms)
    monkeypatch.setattr(AgentHttpTransport, "containers", fake_containers)
    monkeypatch.setattr(AgentHttpTransport, "jobs", fake_jobs)
    monkeypatch.setattr(AgentHttpTransport, "capabilities", fake_capabilities)
    monkeypatch.setattr(AgentHttpTransport, "updates", fake_updates)
    monkeypatch.setattr(AgentHttpTransport, "health", fake_health)
    monkeypatch.setattr(AgentHttpTransport, "orchestration", fake_orchestration)

    assert await integration.async_setup(hass, {})
    result = await _create_entry(hass)
    entry = result["result"]
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    initial = {item.unique_id for item in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert not hass.data[DOMAIN][entry.entry_id].data.connected
    assert not any(item.startswith("vm_") for item in initial)
    assert not any(item.startswith("container_") for item in initial)

    phase["value"] = 1
    await hass.data[DOMAIN][entry.entry_id].async_request_refresh()
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert len(coordinator.data.virtual_machines) == 2
    assert len(coordinator.data.containers) == 10
    assert coordinator.data.virtual_machines[0]["vmid"] == 100
    assert coordinator.data.containers[0]["container_id"] == 200
    recovered = {item.unique_id for item in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert {f"vm_{100 + index}" for index in range(2)} <= recovered
    assert {f"container_{200 + index}_status" for index in range(10)} <= recovered

    await coordinator.async_request_refresh()
    await hass.async_block_till_done()
    assert {item.unique_id for item in er.async_entries_for_config_entry(registry, entry.entry_id)} == recovered

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hasattr(coordinator, "_inventory_entity_manager") or coordinator._inventory_entity_manager is None


async def test_actions_return_read_only_data_and_diagnostics_are_secret_free(hass, patched_transport):
    from custom_components import smart_homelab_maintenance as integration
    assert await integration.async_setup(hass, {})
    result = await _create_entry(hass)
    entry = result["result"]
    await hass.async_block_till_done()
    response = await hass.services.async_call(DOMAIN, "check", {"entry_id": entry.entry_id}, blocking=True, return_response=True)
    assert response["health"]["schema_version"] == "1"
    assert response["capabilities"]["data"]["execution_enabled"] is False
    from custom_components.smart_homelab_maintenance.diagnostics import async_get_config_entry_diagnostics
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["execution_enabled"] is False
    assert "fixture-token" not in str(diagnostics)


async def test_read_only_check_refreshes_coordinator_after_permission_readback(hass, patched_transport, monkeypatch):
    """The card's post-write read-only check must publish a fresh HA state."""
    from custom_components import smart_homelab_maintenance as integration

    assert await integration.async_setup(hass, {})
    result = await _create_entry(hass)
    entry = result["result"]
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    calls = {"count": 0}
    original = coordinator.async_request_refresh

    async def counted_refresh():
        calls["count"] += 1
        return await original()

    monkeypatch.setattr(coordinator, "async_request_refresh", counted_refresh)
    response = await hass.services.async_call(DOMAIN, "check", {"entry_id": entry.entry_id}, blocking=True, return_response=True)
    assert response["health"]["schema_version"] == "1"
    assert calls["count"] == 1


async def test_dry_run_without_entry_id_ignores_setup_metadata_and_returns_response(hass, patched_transport):
    from custom_components import smart_homelab_maintenance as integration

    assert await integration.async_setup(hass, {})
    result = await _create_entry(hass)
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    # Regression guard: setup metadata contains booleans before the entry.
    assert hass.data[DOMAIN]["card_registered"] is True
    response = await hass.services.async_call(
        DOMAIN,
        "dry_run",
        {"target": "host", "confirm": True},
        blocking=True,
        return_response=True,
    )
    assert response["data"]["target"] == "host"
    assert response["data"]["status"] == "simulated"
