"""Prepared read-only Home Assistant actions for the agent API."""

from __future__ import annotations

from typing import Any

from .http_transport import AgentHttpTransport, TransportError

from .const import ACTIONS


async def async_action(transport: AgentHttpTransport, action: str, *, job_id: str | None = None, cursor: int = 0, target: str | None = None, confirm: bool = False) -> dict[str, Any]:
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
    if action == "dry_run":
        if not target or confirm is not True:
            raise ValueError("target and explicit confirmation are required")
        return await transport.dry_run(target)
    raise TransportError("execution_disabled", "preflight is not available until a later gated phase")
