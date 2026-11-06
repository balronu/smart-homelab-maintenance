"""Transport-neutral API models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .errors import ValidationError
from .types import JobRequest


@dataclass(frozen=True, slots=True)
class JobCreatePayload:
    target: str
    operation: str
    expected_version: str | None
    idempotency_key: str
    confirmation_hash: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "JobCreatePayload":
        if not isinstance(payload, Mapping):
            raise ValidationError("JSON body must be an object")
        allowed = {"target", "operation", "expected_version", "idempotency_key", "confirmation_hash"}
        unknown = set(payload) - allowed
        if unknown:
            raise ValidationError("unknown request fields: " + ", ".join(sorted(map(str, unknown))))
        required = {"target", "operation", "idempotency_key"}
        if not required.issubset(payload):
            raise ValidationError("target, operation and idempotency_key are required")
        return cls(
            target=payload["target"],
            operation=payload["operation"],
            expected_version=payload.get("expected_version"),
            idempotency_key=payload["idempotency_key"],
            confirmation_hash=payload.get("confirmation_hash"),
        )

    def to_request(self) -> JobRequest:
        return JobRequest(**asdict(self))


@dataclass(frozen=True, slots=True)
class ApiError:
    code: str
    message: str
    request_id: str | None = None
