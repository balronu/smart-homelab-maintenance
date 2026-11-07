from __future__ import annotations

import socket
import threading
import time
from types import SimpleNamespace

from agent.smart_homelab_maintenance.server import AgentHTTPServer


class _PassthroughContext:
    def wrap_socket(self, sock, *, server_side):
        return sock


def test_server_allows_rebind_after_socket_close_without_reuse_port() -> None:
    assert AgentHTTPServer.allow_reuse_address is True
    assert not getattr(AgentHTTPServer, "allow_reuse_port", False)

    context = _PassthroughContext()
    first = AgentHTTPServer(("127.0.0.1", 0), SimpleNamespace(), context)
    address = first.server_address
    first.server_close()
    second = AgentHTTPServer(address, SimpleNamespace(), context)
    second.server_close()


def test_shutdown_thread_closes_server_loop() -> None:
    server = AgentHTTPServer(("127.0.0.1", 0), SimpleNamespace(), _PassthroughContext())
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    time.sleep(0.02)
    server.shutdown()
    thread.join(timeout=1)
    try:
        assert not thread.is_alive()
    finally:
        server.server_close()


def test_signal_shutdown_contract_is_explicit() -> None:
    source = (__import__("pathlib").Path(__file__).parents[1] / "agent/smart_homelab_maintenance/server.py").read_text(encoding="utf-8")
    assert "signal.SIGTERM" in source and "signal.SIGINT" in source
    assert "threading.Thread(target=server.shutdown" in source
    assert "server.server_close()" in source
