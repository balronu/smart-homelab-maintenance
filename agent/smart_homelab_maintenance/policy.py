"""Versioned fail-closed discovery policy and atomic persistence."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


POLICY_SCHEMA_VERSION = 1


class PolicyMode(str, Enum):
    DISCOVER_ONLY = "discover_only"
    AUTO_ELIGIBLE = "auto_eligible"


class PolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Policy:
    mode: PolicyMode = PolicyMode.DISCOVER_ONLY
    generation: int = 0
    manual_authorized_ids: frozenset[int] = frozenset()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": POLICY_SCHEMA_VERSION,
            "mode": self.mode.value,
            "generation": self.generation,
            "manual_authorized_ids": sorted(self.manual_authorized_ids),
        }


def _ids(value: Any) -> frozenset[int]:
    if not isinstance(value, list):
        raise PolicyError("manual_authorized_ids must be a list")
    result: set[int] = set()
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or not 1 <= item <= 999_999:
            raise PolicyError("manual authorization contains an invalid numeric ID")
        result.add(item)
    return frozenset(result)


def parse_policy(raw: Mapping[str, Any]) -> Policy:
    if raw.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise PolicyError("unsupported policy schema")
    try:
        mode = PolicyMode(raw["mode"])
        generation = raw["generation"]
    except (KeyError, ValueError) as exc:
        raise PolicyError("policy mode or generation is invalid") from exc
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise PolicyError("policy generation is invalid")
    return Policy(mode, generation, _ids(raw.get("manual_authorized_ids", [])))


def load_policy(path: Path, *, require_root: bool = True) -> Policy:
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        if (require_root and path.stat().st_uid != 0) or mode & 0o022:
            raise PolicyError("policy file is not root-owned and safe")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise PolicyError("policy document is not an object")
        return parse_policy(raw)
    except PolicyError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PolicyError("policy is unavailable or malformed") from exc


def save_policy(path: Path, policy: Policy) -> None:
    """Atomically replace a policy candidate; callers must authorize writes."""

    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(policy.as_dict(), handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


class PolicyStore:
    """Small persistent policy boundary owned by the agent process.

    The store is deliberately separate from the root-owned guest allowlist.
    It is only changed through the authenticated API controller, and a missing
    file falls back to the safe discover-only migration default.
    """

    def __init__(self, path: Path, *, initial: Policy | None = None) -> None:
        if not path.is_absolute():
            raise ValueError("policy path must be absolute")
        self.path = path
        self.initial = initial or Policy()

    def read(self) -> Policy:
        if not self.path.exists():
            return self.initial
        return load_policy(self.path, require_root=False)

    def write(self, policy: Policy, *, expected_generation: int, confirmed: bool) -> Policy:
        if not confirmed:
            raise PolicyError("explicit policy confirmation is required")
        current = self.read()
        if current.generation != expected_generation:
            raise PolicyError("policy generation is stale")
        candidate = Policy(policy.mode, expected_generation + 1, policy.manual_authorized_ids)
        save_policy(self.path, candidate)
        return self.read()
