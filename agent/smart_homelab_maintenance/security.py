"""Input validation, secret filtering, and resource gates."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Mapping

from .errors import ResourceGateError, ValidationError
from .types import GateResult, JobRequest, ResourcePolicy, ResourceSnapshot

_ID = re.compile(r"^(?:[a-z][a-z0-9_-]{0,63}|container:[1-9][0-9]{0,5})$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_FORBIDDEN = re.compile(r"[;&|`$<>\n\r]|\b(?:sh|bash|zsh|sudo|pct|ssh|rm|curl|wget)\b", re.I)
_SECRET_KEY = re.compile(r"token|secret|password|passwd|authorization|cookie|api[_-]?key", re.I)


def validate_job_request(request: JobRequest, *, max_version_length: int = 32) -> JobRequest:
    if not isinstance(request, JobRequest):
        raise ValidationError("request must be a JobRequest")
    if not _ID.fullmatch(request.target):
        raise ValidationError("target must be a stable adapter identifier")
    if request.operation not in {"preflight", "plan", "update"}:
        raise ValidationError("operation is not supported")
    if request.expected_version is not None and (
        not isinstance(request.expected_version, str) or len(request.expected_version) > max_version_length
    ):
        raise ValidationError("expected_version is invalid")
    if not _KEY.fullmatch(request.idempotency_key):
        raise ValidationError("idempotency_key is invalid")
    if request.confirmation_hash is not None and not _KEY.fullmatch(request.confirmation_hash):
        raise ValidationError("confirmation_hash is invalid")
    for value in (request.target, request.operation, request.expected_version or ""):
        if _FORBIDDEN.search(value):
            raise ValidationError("request contains forbidden command-like input")
    return request


def resource_gate(snapshot: ResourceSnapshot, policy: ResourcePolicy) -> GateResult:
    checks = (
        (snapshot.free_bytes >= policy.min_free_bytes, "free_space", "free storage below minimum"),
        (
            snapshot.memory_available_bytes is None
            or snapshot.memory_available_bytes >= policy.min_memory_available_bytes,
            "memory_available",
            "available memory below minimum",
        ),
        (
            snapshot.thinpool_percent is None or snapshot.thinpool_percent < policy.max_thinpool_percent,
            "thinpool",
            "thin-pool usage at or above safety limit",
        ),
        (
            policy.max_swap_in_use_bytes is None
            or snapshot.swap_in_use_bytes is None
            or snapshot.swap_in_use_bytes <= policy.max_swap_in_use_bytes,
            "swap",
            "swap usage above safety limit",
        ),
    )
    for passed, code, message in checks:
        if not passed:
            return GateResult(False, code, message, asdict(snapshot))
    return GateResult(True, "ok", "resource gates passed", asdict(snapshot))


def require_resources(snapshot: ResourceSnapshot, policy: ResourcePolicy) -> None:
    result = resource_gate(snapshot, policy)
    if not result.passed:
        raise ResourceGateError(f"{result.code}: {result.message}")


def redact_secrets(value: Any) -> Any:
    """Recursively remove secret-bearing mapping values from logs/results."""

    if isinstance(value, Mapping):
        return {key: "[REDACTED]" if _SECRET_KEY.search(str(key)) else redact_secrets(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, str):
        return _FORBIDDEN.sub("[FILTERED]", value)
    return value
