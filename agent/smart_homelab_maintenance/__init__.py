"""Offline core for Smart Homelab Maintenance.

This package deliberately has no live-system, process, network, or production
configuration integration.  Those boundaries belong to later gated phases.
"""

__all__ = ["adapters", "api", "api_models", "apply_controller", "authorization", "discovery", "discovery_probe", "discovery_socket", "discovery_transport", "errors", "helper_apply_controller", "inventory", "jobs", "orchestration_service", "orchestration_status", "orchestrator", "policy", "reconcile", "security", "types", "versions"]
__version__ = "1.0.0-rc.1"
API_CONTRACT_VERSION = "1.1"
