"""Prepared read-only Home Assistant actions for the agent API."""

from __future__ import annotations

from typing import Any

from agent.smart_homelab_maintenance.http_transport import AgentHttpTransport, TransportError

from .const import ACTIONS


async def async_action(transport: AgentHttpTransport, action: str, *, job_id: str | None = None, cursor: int = 0) -> dict[str, Any]:
    if action not in ACTIONS:
        raise ValueError("unknown action")
    if action == "check":
        return {"health": await transport.health(), "capabilities": await transport.capabilities()}
    if action == "get_job":
        if not job_id:
            raise ValueError("job_id is required")
        return await transport.job(job_id)
    if action == "get_job_events":
        if not job_id:
            raise ValueError("job_id is required")
        return await transport.job_events(job_id, cursor)
    raise TransportError("execution_disabled", "preflight is not available until a later gated phase")
