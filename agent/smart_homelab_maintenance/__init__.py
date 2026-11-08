"""Offline core for Smart Homelab Maintenance.

This package deliberately has no live-system, process, network, or production
configuration integration.  Those boundaries belong to later gated phases.
"""

__all__ = ["adapters", "api", "api_models", "apply_controller", "authorization", "discovery", "discovery_probe", "discovery_socket", "discovery_transport", "errors", "inventory", "jobs", "orchestration_status", "orchestrator", "policy", "reconcile", "security", "types", "versions"]
__version__ = "0.1.0-beta.37"
API_CONTRACT_VERSION = "1.1"
