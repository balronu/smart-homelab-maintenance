"""Structured, secret-safe errors for the offline core."""

from __future__ import annotations


class MaintenanceError(Exception):
    """Base error with a stable public code."""

    code = "maintenance_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(MaintenanceError):
    code = "invalid_request"


class UnknownTargetError(MaintenanceError):
    code = "unknown_target"


class UnsupportedApplicationError(MaintenanceError):
    code = "unsupported_application"


class DuplicateJobError(MaintenanceError):
    code = "duplicate_job"


class InvalidTransitionError(MaintenanceError):
    code = "invalid_job_transition"


class ConcurrentJobError(MaintenanceError):
    code = "target_busy"


class ResourceGateError(MaintenanceError):
    code = "resource_gate_blocked"


class ExecutionDisabledError(MaintenanceError):
    code = "execution_disabled"
