import pytest

from agent.smart_homelab_maintenance.discovery_transport import (
    PROBE_COMMANDS,
    build_request,
    validate_response,
)


def response(container_id=201):
    return {
        "ok": True,
        "container_id": container_id,
        "operation": "probe",
        "result": {
            "os_release": "ID=debian\nVERSION_ID=13\n",
            "apt_version": "apt 3.0.4",
            "dpkg_version": "dpkg-query 1.22.22",
            "apt_exists": "yes",
            "dpkg_exists": "yes",
        },
    }


def test_request_is_numeric_and_fixed_scope():
    assert build_request(201).as_dict() == {"container_id": 201, "operation": "probe"}
    for value in ("201", True, 0, 1_000_000):
        with pytest.raises(ValueError):
            build_request(value)
    assert all(command[0].startswith("/") for command in PROBE_COMMANDS)
    assert all("sh" not in command for command in PROBE_COMMANDS)


def test_response_requires_exact_identity_and_fields():
    assert validate_response(response(), container_id=201)["apt_exists"] == "yes"
    wrong = response(202)
    with pytest.raises(ValueError):
        validate_response(wrong, container_id=201)
    extra = response()
    extra["result"]["command"] = "uname -a"
    with pytest.raises(ValueError):
        validate_response(extra, container_id=201)


def test_response_output_is_bounded():
    oversized = response()
    oversized["result"]["os_release"] = "x" * (64 * 1024)
    with pytest.raises(ValueError):
        validate_response(oversized, container_id=201)
