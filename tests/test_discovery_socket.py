import json

import pytest

from agent.smart_homelab_maintenance.discovery_socket import (
    DiscoverySocketError,
    FixedDiscoveryServer,
    validate_discovery_request,
)


def payload():
    return {
        "os_release": "ID=debian\nVERSION_ID=13\n",
        "apt_version": "apt 3",
        "dpkg_version": "dpkg 1",
        "apt_exists": "yes",
        "dpkg_exists": "yes",
    }


def test_socket_request_is_fixed_and_numeric():
    assert validate_discovery_request({"container_id": 201, "operation": "probe"}) == 201
    for value in ({"container_id": 104, "operation": "simulate"}, {"container_id": "201", "operation": "probe"}, {"container_id": 201, "operation": "probe", "command": "id"}):
        with pytest.raises(DiscoverySocketError):
            validate_discovery_request(value)


def test_server_serializes_probe_and_returns_bounded_structured_result():
    calls = []
    server = FixedDiscoveryServer(probe=lambda cid: calls.append(cid) or payload(), require_root=False)
    result = server.response({"container_id": 201, "operation": "probe"})
    assert result["ok"] is True
    assert calls == [201]
    assert json.loads(json.dumps(result))["result"]["apt_exists"] == "yes"


def test_server_fails_closed_on_bad_probe_output():
    server = FixedDiscoveryServer(probe=lambda cid: {"command": "unexpected"}, require_root=False)
    result = server.response({"container_id": 201, "operation": "probe"})
    assert result == {"ok": False, "error": {"code": "probe_failed"}}
