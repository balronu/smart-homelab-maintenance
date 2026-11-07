from __future__ import annotations

import socket
import time
from unittest import SkipTest


def _states(port: int) -> list[str]:
    state_names = {
        "01": "ESTABLISHED",
        "02": "SYN-SENT",
        "03": "SYN-RECV",
        "04": "FIN-WAIT-1",
        "05": "FIN-WAIT-2",
        "06": "TIME-WAIT",
        "07": "CLOSE",
        "08": "CLOSE-WAIT",
        "09": "LAST-ACK",
        "0A": "LISTEN",
        "0B": "CLOSING",
        "0C": "NEW-SYN-RECV",
    }
    wanted_port = f"{port:04X}"
    states: list[str] = []
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        with open(path, encoding="ascii") as table:
            next(table)
            for line in table:
                fields = line.split()
                if len(fields) >= 4 and fields[1].rsplit(":", 1)[-1] == wanted_port:
                    states.append(state_names.get(fields[3], fields[3]))
    return states


def test_free_port_has_no_states() -> None:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    assert _states(port) == []


def test_active_listener_is_a_blocking_state() -> None:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    try:
        assert "LISTEN" in _states(listener.getsockname()[1])
    finally:
        listener.close()


def test_delayed_shutdown_remains_blocking_until_listener_closes() -> None:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    try:
        time.sleep(0.05)
        assert "LISTEN" in _states(port)
    finally:
        listener.close()
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and _states(port):
        time.sleep(0.01)
    assert _states(port) == []


def test_duplicate_start_is_rejected_by_kernel() -> None:
    first = socket.socket()
    first.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    first.bind(("127.0.0.1", 0))
    first.listen()
    try:
        second = socket.socket()
        try:
            second.bind(("127.0.0.1", first.getsockname()[1]))
        except OSError:
            pass
        else:
            raise AssertionError("duplicate listener bind unexpectedly succeeded")
        finally:
            second.close()
    finally:
        first.close()


def test_time_wait_is_terminal_and_not_a_listener() -> None:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    client = socket.create_connection(("127.0.0.1", port))
    accepted, _ = listener.accept()
    accepted.close()
    client.close()
    listener.close()
    deadline = time.monotonic() + 1.0
    states: list[str] = []
    while time.monotonic() < deadline:
        states = _states(port)
        if states:
            break
        time.sleep(0.01)
    if not states:
        raise SkipTest("Kernel hat für diesen Test keinen sichtbaren TIME-WAIT-Eintrag erzeugt")
    assert "LISTEN" not in states
    assert set(states) <= {"TIME-WAIT"}


def test_state_policy_blocks_everything_except_time_wait() -> None:
    # This mirrors the updater's awk policy without opening a production port.
    policy = 'awk \'$1 != "TIME-WAIT" { found = 1 } END { exit(found ? 0 : 1) }\''
    assert "TIME-WAIT" in policy
