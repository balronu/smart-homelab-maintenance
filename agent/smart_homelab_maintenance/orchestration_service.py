"""Explicit preview/apply orchestration boundary for the authenticated API."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from typing import Any, Mapping

from .discovery import DiscoveryService
from .discovery_probe import DiscoveryProbeTransport
from .orchestrator import LxcOrchestrator, OrchestrationResult
from .orchestration_status import OrchestrationStatus
from .policy import Policy, PolicyError, PolicyMode, PolicyStore, parse_policy


@dataclass(frozen=True, slots=True)
class Preview:
    token: str
    result: OrchestrationResult


class OrchestrationService:
    """Serializes policy changes and rejects stale apply plans."""

    def __init__(self, discovery: DiscoveryService, policy_store: PolicyStore,
                 orchestrator: LxcOrchestrator, probe_transport: DiscoveryProbeTransport | None,
                 *, status: OrchestrationStatus | None = None,
                 authorized_ids_reader=None) -> None:
        self.discovery = discovery
        self.policy_store = policy_store
        self.orchestrator = orchestrator
        self.probe_transport = probe_transport
        self.status = status or orchestrator.status
        self.authorized_ids_reader = authorized_ids_reader
        self._lock = threading.Lock()
        self._preview: Preview | None = None

    def policy(self) -> dict[str, Any]:
        return self.policy_store.read().as_dict()

    def prepare_policy(self, request: Mapping[str, Any]) -> dict[str, Any]:
        policy = self._candidate(request)
        current = self.policy_store.read()
        if request.get("generation") != current.generation:
            raise PolicyError("policy generation is stale")
        return {"current": current.as_dict(), "candidate": policy.as_dict(), "requires_confirmation": True}

    def apply_policy(self, request: Mapping[str, Any]) -> dict[str, Any]:
        current = self.policy_store.read()
        if request.get("generation") != current.generation:
            raise PolicyError("policy generation is stale")
        candidate = self._candidate(request)
        updated = self.policy_store.write(candidate, expected_generation=current.generation, confirmed=request.get("confirm") is True)
        return {"policy": updated.as_dict(), "read_back": True}

    def preview(self) -> dict[str, Any]:
        with self._lock:
            policy = self.policy_store.read()
            records = [item.as_dict() for item in self.discovery.containers()]
            existing = self._existing_ids()
            result = self.orchestrator.run(records, policy=policy, transport=self.probe_transport,
                                           existing_authorized_ids=existing, confirmed=False)
            token = self._token(result)
            self._preview = Preview(token, result)
            return {"preview_token": token, **result.as_dict(), "requires_confirmation": True}

    def apply(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if request.get("confirm") is not True:
            raise PolicyError("explicit apply confirmation is required")
        token = request.get("preview_token")
        with self._lock:
            if not self._preview or token != self._preview.token:
                raise PolicyError("preview is missing or stale")
            # Rebuild the plan from current inventory and probes before writing.
            policy = self.policy_store.read()
            records = [item.as_dict() for item in self.discovery.containers()]
            fresh = self.orchestrator.run(records, policy=policy, transport=self.probe_transport,
                                          existing_authorized_ids=self._existing_ids(), confirmed=False)
            if self._token(fresh) != token:
                raise PolicyError("preview is stale; run a new preview")
            result = self.orchestrator.run(records, policy=policy, transport=self.probe_transport,
                                           existing_authorized_ids=self._existing_ids(), confirmed=True)
            self._preview = None
            return {"preview_token": token, **result.as_dict(), "read_back_required": True}

    def _existing_ids(self) -> set[int]:
        if self.authorized_ids_reader is not None:
            return set(self.authorized_ids_reader())
        return set(self.status.authorized_container_ids)

    @staticmethod
    def _candidate(request: Mapping[str, Any]) -> Policy:
        if set(request) - {"mode", "generation", "manual_authorized_ids", "confirm"}:
            raise PolicyError("policy request contains unsupported fields")
        try:
            mode = PolicyMode(str(request["mode"]))
        except (KeyError, ValueError) as exc:
            raise PolicyError("policy mode is invalid") from exc
        ids = request.get("manual_authorized_ids", [])
        return parse_policy({"schema_version": 1, "mode": mode.value, "generation": 0, "manual_authorized_ids": ids})

    @staticmethod
    def _token(result: OrchestrationResult) -> str:
        value = result.reconcile.as_dict()
        # observed_at is informational and must not make an unchanged plan
        # stale between preview and the confirmation read-back.
        value.pop("observed_at", None)
        payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()
