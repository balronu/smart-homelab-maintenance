"""Allowlist apply adapter that never gives the agent direct root-file access."""

from __future__ import annotations

from typing import Any

from .apply_controller import ApplyResult
from .authorization import AllowlistPlan
from .permissions import PolicyHelperTransport


class HelperAllowlistApplyController:
    def __init__(self, helper: PolicyHelperTransport) -> None:
        self.helper = helper

    def preview(self, plan: AllowlistPlan) -> ApplyResult:
        return ApplyResult(False, True, tuple(sorted(plan.authorized_ids)))

    def apply(self, plan: AllowlistPlan, *, confirmed: bool = False) -> ApplyResult:
        if not confirmed:
            return self.preview(plan)
        entries: dict[str, dict[str, Any]] = {}
        for item in plan.entries:
            if not item.authorized:
                continue
            entries[str(item.container_id)] = {
                "authorized": True,
                "simulation_authorized": True,
                "update_authorized": False,
                "os_name": item.os_name,
                "os_version": item.os_version,
                "package_manager": item.package_manager or "apt",
            }
        try:
            self.helper.apply_allowlist(entries)
            read_back = self.helper.read()
            actual = {
                int(raw_id) for raw_id, values in read_back.items()
                if values.get("authorized") is True or values.get("simulation_authorized") is True
            }
            update_ids = {int(raw_id) for raw_id, values in read_back.items() if values.get("update_authorized") is True}
            if actual != set(plan.authorized_ids) or update_ids:
                return ApplyResult(False, False, tuple(sorted(plan.authorized_ids)), "helper_readback_mismatch")
        except Exception:  # fail closed; helper owns the error detail
            return ApplyResult(False, False, tuple(sorted(plan.authorized_ids)), "helper_apply_failed")
        return ApplyResult(True, True, tuple(sorted(plan.authorized_ids)))
