"""Explicit application adapter registry.

The registry contains metadata only.  No adapter in Phase 2.1 executes a
command or opens a network connection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .errors import UnknownTargetError, UnsupportedApplicationError
from .types import InstallKind


@dataclass(frozen=True, slots=True)
class AdapterSpec:
    app_id: str
    display_name: str
    install_kind: InstallKind
    supported: bool
    execution_enabled: bool = False
    capabilities: frozenset[str] = frozenset({"discover", "preflight", "plan"})
    discovery_supported: bool = True
    version_check_supported: bool = True
    preflight_supported: bool = False
    update_supported: bool = False
    rollback_supported: bool = False
    blocked_reasons: tuple[str, ...] = ()

    def capability_dict(self) -> dict[str, object]:
        return {
            "discovery_supported": self.discovery_supported,
            "version_check_supported": self.version_check_supported,
            "preflight_supported": self.preflight_supported,
            "update_supported": self.update_supported,
            "execution_enabled": self.execution_enabled,
            "rollback_supported": self.rollback_supported,
            "blocked_reasons": list(self.blocked_reasons),
        }


class AdapterRegistry:
    def __init__(self, specs: Mapping[str, AdapterSpec] | None = None) -> None:
        self._specs = dict(specs or {})

    def register(self, spec: AdapterSpec) -> None:
        if not spec.app_id or "/" in spec.app_id or " " in spec.app_id:
            raise ValueError("adapter app_id must be a simple stable identifier")
        if spec.execution_enabled and "execute" not in spec.capabilities:
            raise ValueError("execute capability is required when execution is enabled")
        self._specs[spec.app_id] = spec

    def get(self, app_id: str) -> AdapterSpec:
        try:
            return self._specs[app_id]
        except KeyError as exc:
            raise UnknownTargetError(f"unknown adapter target: {app_id}") from exc

    def require_supported(self, app_id: str) -> AdapterSpec:
        spec = self.get(app_id)
        if not spec.supported:
            raise UnsupportedApplicationError(f"adapter is not supported: {app_id}")
        return spec

    def all(self) -> tuple[AdapterSpec, ...]:
        return tuple(self._specs.values())


def default_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register(AdapterSpec("zigbee2mqtt_home", "Zigbee2MQTT Zuhause", InstallKind.GIT_SYSTEMD, True, preflight_supported=True, update_supported=True))
    registry.register(AdapterSpec("zigbee2mqtt_womo", "Zigbee2MQTT Wohnmobil", InstallKind.GIT_SYSTEMD, False, blocked_reasons=("known_dirty_git_state",)))
    registry.register(AdapterSpec("paperless", "Paperless-ngx", InstallKind.UV_SYSTEMD, True, preflight_supported=True, update_supported=True))
    registry.register(AdapterSpec("cloudflared", "Cloudflared", InstallKind.APT, False, blocked_reasons=("no_application_adapter",)))
    registry.register(AdapterSpec("nginx_proxy_manager", "Nginx Proxy Manager", InstallKind.DOCKER, False, blocked_reasons=("unsupported_install_kind",)))
    return registry
