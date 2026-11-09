"""Bounded Home Assistant actions for the agent API."""

from __future__ import annotations

from typing import Any

from .http_transport import AgentHttpTransport, TransportError

from .const import ACTIONS


async def async_action(transport: AgentHttpTransport, action: str, *, job_id: str | None = None, cursor: int = 0, target: str | None = None, confirm: bool = False, plan_digest: str | None = None, simulation_authorized: bool = False, update_authorized: bool = False, mode: str | None = None, generation: int | None = None, preview_token: str | None = None, manual_authorized_ids: list[int] | None = None) -> dict[str, Any]:
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
    if action == "execute":
        if not target or confirm is not True:
            raise ValueError("target and explicit confirmation are required")
        return await transport.execute_update(target, plan_digest=plan_digest)
    if action == "set_permissions":
        if not target or confirm is not True:
            raise ValueError("target and explicit confirmation are required")
        return await transport.set_permissions(target, simulation_authorized=simulation_authorized, update_authorized=update_authorized)
    if action == "policy_prepare":
        if mode not in {"discover_only", "auto_eligible"} or generation is None:
            raise ValueError("mode and generation are required")
        return await transport.policy_prepare(mode=mode, generation=generation, manual_authorized_ids=manual_authorized_ids)
    if action == "policy_apply":
        if mode not in {"discover_only", "auto_eligible"} or generation is None or confirm is not True:
            raise ValueError("mode, generation and explicit confirmation are required")
        return await transport.policy_apply(mode=mode, generation=generation, confirm=True, manual_authorized_ids=manual_authorized_ids)
    if action == "orchestration_preview":
        return await transport.orchestration_preview()
    if action == "orchestration_apply":
        if not preview_token or confirm is not True:
            raise ValueError("preview token and explicit confirmation are required")
        return await transport.orchestration_apply(preview_token=preview_token, confirm=True)
    raise TransportError("execution_disabled", "preflight is not available until a later gated phase")
