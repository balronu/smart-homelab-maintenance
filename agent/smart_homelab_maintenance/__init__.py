"""Offline core for Smart Homelab Maintenance.

This package deliberately has no live-system, process, network, or production
configuration integration.  Those boundaries belong to later gated phases.
"""

__all__ = ["adapters", "api", "api_models", "authorization", "discovery", "errors", "inventory", "jobs", "security", "types", "versions"]
__version__ = "0.1.0-beta.31"
API_CONTRACT_VERSION = "1.1"
