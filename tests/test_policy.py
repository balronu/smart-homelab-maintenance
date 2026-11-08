import json
import os
import stat

import pytest

from agent.smart_homelab_maintenance.policy import (
    Policy,
    PolicyError,
    PolicyMode,
    load_policy,
    parse_policy,
    save_policy,
)


def test_policy_defaults_are_explicit_and_versioned():
    policy = Policy()
    assert policy.mode is PolicyMode.DISCOVER_ONLY
    assert policy.as_dict()["schema_version"] == 1
    assert parse_policy(policy.as_dict()) == policy


def test_policy_rejects_bad_schema_mode_and_ids():
    with pytest.raises(PolicyError):
        parse_policy({"schema_version": 99, "mode": "discover_only", "generation": 0})
    with pytest.raises(PolicyError):
        parse_policy({"schema_version": 1, "mode": "anything", "generation": 0})
    with pytest.raises(PolicyError):
        parse_policy({"schema_version": 1, "mode": "auto_eligible", "generation": 0, "manual_authorized_ids": ["201"]})


def test_policy_persistence_is_atomic_and_private(tmp_path):
    path = tmp_path / "state" / "policy.json"
    save_policy(path, Policy(PolicyMode.AUTO_ELIGIBLE, 4, frozenset({201})))
    assert load_policy(path).mode is PolicyMode.AUTO_ELIGIBLE
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert path.stat().st_uid == os.getuid()
    assert json.loads(path.read_text())["generation"] == 4


def test_load_policy_fails_closed_for_unsafe_mode(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(Policy().as_dict()))
    path.chmod(0o644)
    with pytest.raises(PolicyError):
        load_policy(path)
