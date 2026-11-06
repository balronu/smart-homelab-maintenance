"""Deliberately disabled execution boundary for Phase 2.1."""

from __future__ import annotations

from .adapters import AdapterRegistry
from .errors import ExecutionDisabledError
from .types import JobRequest


class ExecutionController:
    def __init__(self, registry: AdapterRegistry, *, enabled: bool = False) -> None:
        self.registry = registry
        self.enabled = enabled

    def execute(self, request: JobRequest) -> None:
        spec = self.registry.require_supported(request.target)
        if not self.enabled or not spec.execution_enabled:
            raise ExecutionDisabledError("update execution is disabled in the offline foundation")
        raise ExecutionDisabledError("no live executor is implemented in Phase 2.1")
