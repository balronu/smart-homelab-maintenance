"""Offline Proxmox and application discovery using injectable mock backends."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Protocol

from .adapters import AdapterRegistry, AdapterSpec, default_registry
from .types import InstallKind


@dataclass(frozen=True, slots=True)
class ApplicationObservation:
    app_id: str
    display_name: str
    container_id: int
    install_kind: InstallKind
    installed_version: str | None
    available_version: str | None = None
    update_supported: bool = False
    blocked_reasons: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["install_kind"] = self.install_kind.value
        result["blocked_reasons"] = list(self.blocked_reasons)
        return result


@dataclass(frozen=True, slots=True)
class ContainerObservation:
    container_id: int
    name: str
    running: bool
    os_name: str
    os_version: str
    memory_available_bytes: int | None
    free_bytes: int | None
    package_manager: str | None
    applications: tuple[ApplicationObservation, ...] = ()
    blocked_reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["applications"] = [app.as_dict() for app in self.applications]
        result["blocked_reasons"] = list(self.blocked_reasons)
        return result


class ProxmoxDiscoveryBackend(Protocol):
    def containers(self) -> list[Mapping[str, Any]]: ...

    def host(self) -> Mapping[str, Any]: ...

    def virtual_machines(self) -> list[Mapping[str, Any]]: ...


class FixtureProxmoxBackend:
    """A deterministic backend; it never calls Proxmox or a shell."""

    def __init__(self, fixture: list[Mapping[str, Any]]) -> None:
        self._fixture = fixture

    def containers(self) -> list[Mapping[str, Any]]:
        return [dict(item) for item in self._fixture]

    def host(self) -> Mapping[str, Any]:
        return {"name": "fixture", "release": "unknown", "kernel": "unknown", "online": True}

    def virtual_machines(self) -> list[Mapping[str, Any]]:
        return []


def phase1_fixture() -> list[dict[str, Any]]:
    """Sanitized representative inventory from Phase 1."""
    return [
        {"container_id": 101, "name": "cloudflared", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt", "applications": [{"app_id": "cloudflared", "version": "2025.1"}]},
        {"container_id": 102, "name": "zigbee2mqtt-haus", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt", "applications": [{"app_id": "zigbee2mqtt_home", "version": "2.14.2", "details": {"repository": "/opt/zigbee2mqtt", "branch": "master", "git_clean": True, "node": "24.22.2", "pnpm": "10", "service": "zigbee2mqtt"}}]},
        {"container_id": 103, "name": "mariadb", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt", "applications": []},
        {"container_id": 105, "name": "openclaw", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt", "applications": []},
        {"container_id": 107, "name": "paperless", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt", "applications": [{"app_id": "paperless", "version": "2.14", "details": {"install": "uv", "python": "3.12", "postgresql": "16", "redis": True, "services": ["paperless-web", "paperless-worker"], "data_dir": "/opt/paperless", "migration_risk": True, "manual_recovery_required": False}}]},
        {"container_id": 108, "name": "zigbee2mqtt-wohnmobil", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt", "applications": [{"app_id": "zigbee2mqtt_womo", "version": "2.14.2", "details": {"repository": "/opt/zigbee2mqtt", "git_clean": False, "local_changes": True, "service": "zigbee2mqtt"}}]},
        {"container_id": 109, "name": "mqtt", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt", "applications": []},
        {"container_id": 110, "name": "npm", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt", "applications": [{"app_id": "nginx_proxy_manager", "version": None}]},
        {"container_id": 111, "name": "proxmox-touch-dashboard", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt", "applications": []},
        {"container_id": 112, "name": "stellantis-oauth-worker", "running": True, "os_name": "Debian", "os_version": "12", "package_manager": "apt", "applications": []},
    ]


class DiscoveryService:
    def __init__(self, backend: ProxmoxDiscoveryBackend, registry: AdapterRegistry | None = None) -> None:
        self.backend = backend
        self.registry = registry or default_registry()

    def containers(self) -> list[ContainerObservation]:
        result = []
        for raw in self.backend.containers():
            apps = tuple(self._app(raw, app) for app in raw.get("applications", []))
            reasons = tuple(reason for app in apps for reason in app.blocked_reasons)
            result.append(ContainerObservation(
                container_id=int(raw["container_id"]), name=str(raw["name"]), running=bool(raw.get("running", False)),
                os_name=str(raw.get("os_name", "unknown")), os_version=str(raw.get("os_version", "unknown")),
                memory_available_bytes=raw.get("memory_available_bytes"), free_bytes=raw.get("free_bytes"),
                package_manager=raw.get("package_manager"), applications=apps, blocked_reasons=tuple(sorted(set(reasons))),
            ))
        return result

    def app(self, app_id: str) -> ApplicationObservation:
        for container in self.containers():
            for app in container.applications:
                if app.app_id == app_id:
                    return app
        raise KeyError(app_id)

    def host(self) -> dict[str, Any]:
        return dict(self.backend.host())

    def virtual_machines(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.backend.virtual_machines()]

    def _app(self, raw: Mapping[str, Any], item: Mapping[str, Any]) -> ApplicationObservation:
        app_id = str(item["app_id"])
        spec: AdapterSpec = self.registry.get(app_id)
        details = dict(item.get("details", {}))
        reasons = list(spec.blocked_reasons)
        if details.get("manual_recovery_required"):
            reasons.append("manual_recovery_required")
        if details.get("git_clean") is False:
            reasons.append("dirty_git_state")
        if not raw.get("running", False):
            reasons.append("container_stopped")
        return ApplicationObservation(app_id, spec.display_name, int(raw["container_id"]), spec.install_kind,
            item.get("version"), item.get("available_version"), spec.update_supported and not reasons,
            tuple(sorted(set(reasons))), details)
