"""Bounded, authenticated API surface for offline tests.

The application exposes an in-process handler and an optional localhost-only
stdlib server.  It has no production listener configuration.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict
from typing import Any, Mapping

from .api_models import ApiError
from .discovery import DiscoveryService
from .errors import MaintenanceError, ValidationError
from .jobs import JobRepository
from .security import redact_secrets
from .updates import UpdateService
from . import API_CONTRACT_VERSION, __version__


class ApiApplication:
    def __init__(self, discovery: DiscoveryService, jobs: JobRepository, *, updates: UpdateService | None = None, read_token: str | None = None, max_bytes: int = 256_000, orchestration_status: Any | None = None, orchestration: Any | None = None) -> None:
        self.discovery = discovery
        self.jobs = jobs
        self.updates = updates
        self.read_token = read_token
        self.max_bytes = max_bytes
        self.orchestration_status = orchestration_status
        self.orchestration = orchestration

    def handle(self, method: str, path: str, *, headers: Mapping[str, str] | None = None, body: bytes | None = None) -> tuple[int, dict[str, Any]]:
        request_id = secrets.token_hex(8)
        headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        raw_path, separator, raw_query = path.partition("?")
        query: dict[str, list[str]] = {}
        if separator:
            for item in raw_query.split("&"):
                key, equals, value = item.partition("=")
                if key:
                    query.setdefault(key, []).append(value if equals else "")
        try:
            method = method.upper()
            if method not in {"GET", "POST"}:
                raise ValidationError("method is not supported")
            if raw_path != "/api/v1/health" and not self._authorized(headers):
                return 401, self._error("authentication_required", "authentication required", request_id)
            payload = self._route(raw_path, query, method=method, body=body or b"")
            body = {"schema_version": "1", "data": payload, "request_id": request_id}
            encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
            if len(encoded) > self.max_bytes:
                return 413, self._error("response_too_large", "response exceeds configured limit", request_id)
            return 200, body
        except KeyError:
            return 404, self._error("not_found", "resource not found", request_id)
        except MaintenanceError as exc:
            return 400, self._error(exc.code, str(exc), request_id)
        except (TypeError, ValueError) as exc:
            return 400, self._error("invalid_parameter", str(exc), request_id)

    def _authorized(self, headers: Mapping[str, str]) -> bool:
        supplied = headers.get("authorization", "")
        return bool(self.read_token and secrets.compare_digest(supplied, "Bearer " + self.read_token))

    def _route(self, path: str, query: Mapping[str, list[str]], *, method: str, body: bytes) -> Any:
        if path == "/api/v1/health":
            return {"status": "ok", "mode": "offline", "agent_version": __version__, "api_contract": API_CONTRACT_VERSION}
        if path == "/api/v1/capabilities":
            return {"execution_enabled": bool(getattr(self.updates, "execution_enabled", False)), "dry_run_enabled": self.updates is not None, "adapters": [{"app_id": s.app_id, **s.capability_dict()} for s in self.discovery.registry.all()]}
        if path == "/api/v1/orchestration":
            if self.orchestration_status is None:
                return {"status": "unavailable", "policy_mode": "discover_only"}
            current_status = self.orchestration_status() if callable(self.orchestration_status) else self.orchestration_status
            value = current_status.as_dict() if hasattr(current_status, "as_dict") else dict(current_status)
            ready = value.get("helper_installed") is True and value.get("discovery_socket_active") is True and value.get("integrity_ok") is True
            return {"status": "ok" if ready else "unavailable", **value}
        if path == "/api/v1/policy" and method == "GET":
            if self.orchestration is None:
                raise ValidationError("orchestration is unavailable")
            return self.orchestration.policy()
        if path == "/api/v1/host":
            return self.discovery.host()
        if path == "/api/v1/virtual-machines":
            return self._page(self.discovery.virtual_machines(), query)
        if path == "/api/v1/containers":
            return self._page([item.as_dict() for item in self.discovery.containers()], query)
        if path == "/api/v1/jobs":
            return self._page(self.jobs.list(offset=self._int(query, "offset", 0), limit=self._int(query, "limit", 50)), query)
        if path == "/api/v1/updates" and method == "GET":
            if self.updates is None:
                return {"items": [], "status": "unknown"}
            items = self.updates.all()
            return {"items": items, "checked_at": max((item.get("checked_at") or "" for item in items), default=None)}
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:3] == ["api", "v1", "updates"] and method == "GET":
            if self.updates is None:
                return {"status": "unknown", "error": "update checks are unavailable"}
            return self.updates.check(parts[3]).as_dict()
        if len(parts) == 5 and parts[:3] == ["api", "v1", "updates"] and parts[4] == "dry-run" and method == "POST":
            if self.updates is None:
                return {"simulation": True, "success": False, "safe": False, "error": "dry run is unavailable"}
            try:
                request = json.loads(body.decode("utf-8")) if body else {}
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValidationError("dry-run body must be valid JSON") from exc
            if not isinstance(request, dict) or set(request) - {"confirm"}:
                raise ValidationError("dry-run accepts only confirm")
            return self.updates.dry_run(parts[3], confirmed=request.get("confirm") is True)
        if len(parts) == 5 and parts[:3] == ["api", "v1", "updates"] and parts[4] in {"execute", "update"} and method == "POST":
            if self.updates is None:
                return {"target": parts[3], "success": False, "safe": False, "error": "update execution is unavailable"}
            try:
                request = json.loads(body.decode("utf-8")) if body else {}
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValidationError("update body must be valid JSON") from exc
            if not isinstance(request, dict) or set(request) - {"confirm", "install_confirmed", "plan_digest"}:
                raise ValidationError("update accepts confirm, install_confirmed and plan_digest")
            return self.updates.execute_update(parts[3], confirmed=request.get("confirm") is True, install_confirmed=request.get("install_confirmed") is True, plan_digest=request.get("plan_digest"))
        if len(parts) == 5 and parts[:3] == ["api", "v1", "updates"] and parts[4] == "permissions" and method == "POST":
            if self.updates is None:
                raise ValidationError("permission management is unavailable")
            try:
                request = json.loads(body.decode("utf-8")) if body else {}
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValidationError("permission body must be valid JSON") from exc
            allowed = {"confirm", "simulation_authorized", "update_authorized"}
            if not isinstance(request, dict) or set(request) - allowed or not isinstance(request.get("simulation_authorized"), bool) or not isinstance(request.get("update_authorized"), bool):
                raise ValidationError("permissions accepts confirm and two boolean authorization fields")
            return self.updates.set_permissions(parts[3], simulation_authorized=request["simulation_authorized"], update_authorized=request["update_authorized"], confirmed=request.get("confirm") is True)
        if path in {"/api/v1/update", "/api/v1/execute"}:
            raise ValidationError("use the target-scoped, confirmed update endpoint")
        if path in {"/api/v1/policy/prepare", "/api/v1/policy/apply"} and method == "POST":
            if self.orchestration is None:
                raise ValidationError("orchestration is unavailable")
            request = self._json_object(body, "policy")
            return (self.orchestration.prepare_policy(request) if path.endswith("/prepare")
                    else self.orchestration.apply_policy(request))
        if path == "/api/v1/orchestration/preview" and method == "POST":
            if self.orchestration is None:
                raise ValidationError("orchestration is unavailable")
            request = self._json_object(body, "preview")
            if request:
                raise ValidationError("preview accepts an empty JSON object only")
            return self.orchestration.preview()
        if path == "/api/v1/orchestration/apply" and method == "POST":
            if self.orchestration is None:
                raise ValidationError("orchestration is unavailable")
            return self.orchestration.apply(self._json_object(body, "apply"))
        if len(parts) == 4 and parts[:3] == ["api", "v1", "apps"]:
            return self.discovery.app(parts[3]).as_dict()
        if len(parts) == 4 and parts[:3] == ["api", "v1", "jobs"]:
            return self.jobs.get(parts[3])
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "cancel" and method == "POST":
            if self.updates is None:
                raise ValidationError("job cancellation is unavailable")
            request = self._json_object(body, "cancel")
            if set(request) - {"confirm"}:
                raise ValidationError("cancel accepts confirm")
            return self.updates.cancel_job(parts[3], confirmed=request.get("confirm") is True)
        if len(parts) == 5 and parts[:3] == ["api", "v1", "jobs"] and parts[4] == "events":
            return {"events": self.jobs.events(parts[3], after=self._int(query, "after", 0), limit=self._int(query, "limit", min(50, self.jobs.max_log_entries)))}
        raise KeyError(path)

    @staticmethod
    def _int(query: Mapping[str, list[str]], name: str, default: int) -> int:
        value = query.get(name, [str(default)])[0]
        if not value.isdigit():
            raise ValidationError(f"{name} must be a non-negative integer")
        return int(value)

    @staticmethod
    def _page(items: list[Any], query: Mapping[str, list[str]]) -> dict[str, Any]:
        offset = ApiApplication._int(query, "offset", 0)
        limit = ApiApplication._int(query, "limit", 50)
        if limit < 1 or limit > 100:
            raise ValidationError("limit must be between 1 and 100")
        return {"items": items[offset:offset + limit], "offset": offset, "limit": limit, "total": len(items), "has_more": offset + limit < len(items)}

    @staticmethod
    def _error(code: str, message: str, request_id: str) -> dict[str, Any]:
        return {"schema_version": "1", "error": asdict(ApiError(code, str(redact_secrets(message)), request_id))}

    @staticmethod
    def _json_object(body: bytes, operation: str) -> dict[str, Any]:
        try:
            value = json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(f"{operation} body must be valid JSON") from exc
        if not isinstance(value, dict):
            raise ValidationError(f"{operation} body must be a JSON object")
        return value
