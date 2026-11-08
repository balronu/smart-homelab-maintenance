from agent.smart_homelab_maintenance.discovery_probe import ProbeState, evaluate_probe, parse_os_release


def record(container_id=201, running=True):
    return {"container_id": container_id, "running": running}


class Transport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def probe(self, container_id):
        self.calls.append(container_id)
        return self.payload


def test_safe_default_never_calls_transport():
    transport = Transport({"os_release": "ID=debian\nVERSION_ID=13\n", "apt_version": "apt 3", "dpkg_version": "dpkg 1"})
    result = evaluate_probe(record(), transport=transport, discovery_enabled=False)
    assert result.state is ProbeState.UNAUTHORIZED
    assert transport.calls == []


def test_debian_probe_passes_with_complete_evidence():
    transport = Transport({"os_release": "ID=debian\nVERSION_ID=13\n", "apt_version": "apt 3.0.4", "dpkg_version": "dpkg 1.22"})
    result = evaluate_probe(record(), transport=transport, discovery_enabled=True)
    assert result.state is ProbeState.PASS
    assert transport.calls == [201]


def test_ubuntu_is_supported_and_other_os_is_not():
    ubuntu = Transport({"os_release": "ID=ubuntu\nVERSION_ID=24.04\n", "apt_version": "apt 2", "dpkg_version": "dpkg 1"})
    alpine = Transport({"os_release": "ID=alpine\nVERSION_ID=3.20\n", "apt_version": "apk", "dpkg_version": ""})
    assert evaluate_probe(record(201), transport=ubuntu, discovery_enabled=True).state is ProbeState.PASS
    assert evaluate_probe(record(202), transport=alpine, discovery_enabled=True).state is ProbeState.UNSUPPORTED


def test_stopped_invalid_missing_and_malformed_evidence_are_safe():
    transport = Transport({"os_release": "ID=debian\nVERSION_ID=13\n", "apt_version": "apt 3", "dpkg_version": "dpkg 1"})
    assert evaluate_probe(record(201, running=False), transport=transport, discovery_enabled=True).state is ProbeState.STOPPED
    assert evaluate_probe(record("201"), transport=transport, discovery_enabled=True).state is ProbeState.PROBE_FAILED
    missing = Transport({"os_release": "ID=debian\n", "apt_version": "", "dpkg_version": ""})
    assert evaluate_probe(record(202), transport=missing, discovery_enabled=True).state is ProbeState.UNKNOWN
    malformed = Transport({"os_release": "ID=debian\nVERSION_ID=13\n", "apt_version": "x" * 70000, "dpkg_version": "dpkg"})
    assert evaluate_probe(record(203), transport=malformed, discovery_enabled=True).state is ProbeState.PROBE_FAILED


def test_os_release_parser_ignores_untrusted_keys_and_invalid_values():
    assert parse_os_release("NAME=evil\nID=debian\nVERSION_ID='13'\n") == ("debian", "13")
    assert parse_os_release("ID=debian;rm\nVERSION_ID=13\n") == (None, "13")
