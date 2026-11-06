"""Offline container/application inventory catalog."""

from __future__ import annotations

from .errors import UnknownTargetError
from .types import ApplicationRef, ContainerRef


class InventoryCatalog:
    def __init__(self) -> None:
        self._containers: dict[int, ContainerRef] = {}
        self._applications: dict[str, ApplicationRef] = {}

    def add_container(self, container: ContainerRef) -> None:
        self._containers[container.container_id] = container

    def add_application(self, application: ApplicationRef) -> None:
        if application.container_id not in self._containers:
            raise UnknownTargetError(f"unknown container: {application.container_id}")
        self._applications[application.app_id] = application

    def container(self, container_id: int) -> ContainerRef:
        try:
            return self._containers[container_id]
        except KeyError as exc:
            raise UnknownTargetError(f"unknown container: {container_id}") from exc

    def application(self, app_id: str) -> ApplicationRef:
        try:
            return self._applications[app_id]
        except KeyError as exc:
            raise UnknownTargetError(f"unknown application: {app_id}") from exc

    def containers(self) -> tuple[ContainerRef, ...]:
        return tuple(self._containers.values())

    def applications(self) -> tuple[ApplicationRef, ...]:
        return tuple(self._applications.values())
