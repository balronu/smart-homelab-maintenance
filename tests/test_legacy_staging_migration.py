import json
import os
import sys
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from unittest.mock import patch
from pathlib import Path
import importlib.util


SCRIPT = Path(__file__).parents[1] / "scripts" / "migrate-legacy-staging.py"
SPEC = importlib.util.spec_from_file_location("legacy_migration", SCRIPT)
MIGRATION = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MIGRATION)


def run(tmp_path, *args):
    stdout = StringIO()
    stderr = StringIO()
    with patch.object(sys, "argv", [str(SCRIPT), *args]), patch.object(MIGRATION.os, "geteuid", return_value=0):
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                MIGRATION.main()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
            if isinstance(exc.code, str):
                stderr.write(exc.code)
            return type("Result", (), {"returncode": code, "stdout": stdout.getvalue(), "stderr": stderr.getvalue()})()
    return type("Result", (), {"returncode": 0, "stdout": stdout.getvalue(), "stderr": stderr.getvalue()})()


def fixture(tmp_path, names=("agent.previous.1.staging", "agent.failed.2.staging")):
    agent_root = tmp_path / "agent-root"
    state_root = tmp_path / "state-root"
    (agent_root / "agent" / "smart_homelab_maintenance").mkdir(parents=True)
    (agent_root / "agent" / "smart_homelab_maintenance" / "__init__.py").write_text("__version__ = '1.0.6'\n")
    candidates = []
    for name in names:
        path = agent_root / name
        path.mkdir()
        (path / "payload").write_text(name)
        candidates.append(str(path))
    state_root.mkdir()
    return agent_root, state_root, candidates


def test_preflight_requires_explicit_legacy_candidates_and_writes_complete_plan(tmp_path):
    agent_root, state_root, candidates = fixture(tmp_path)
    plan = tmp_path / "plan.json"
    result = run(tmp_path, "--preflight", "--plan-file", str(plan), "--agent-root", str(agent_root), "--state-root", str(state_root), "--candidate", candidates[0], "--candidate", candidates[1])
    assert result.returncode == 0, result.stderr
    payload = json.loads(plan.read_text())
    assert [item["name"] for item in payload["candidates"]] == ["agent.previous.1.staging", "agent.failed.2.staging"]
    assert all(not item["identity_present"] for item in payload["candidates"])
    assert all(item["symlinks"] == [] and item["process_refs"] == [] for item in payload["candidates"])


def test_apply_is_fail_closed_when_manifest_changes(tmp_path):
    agent_root, state_root, candidates = fixture(tmp_path)
    plan = tmp_path / "plan.json"
    assert run(tmp_path, "--preflight", "--plan-file", str(plan), "--agent-root", str(agent_root), "--state-root", str(state_root), "--candidate", candidates[0], "--candidate", candidates[1]).returncode == 0
    (Path(candidates[0]) / "payload").write_text("tampered")
    result = run(tmp_path, "--apply", "--confirm", "--plan-file", str(plan), "--agent-root", str(agent_root), "--state-root", str(state_root), "--quarantine-root", str(state_root / "staging-quarantine"))
    assert result.returncode != 0
    assert Path(candidates[0]).exists()
    assert not (state_root / "staging-quarantine" / Path(candidates[0]).name).exists()


def test_apply_is_idempotent_and_resumes_after_partial_completion(tmp_path):
    agent_root, state_root, candidates = fixture(tmp_path)
    plan = tmp_path / "plan.json"
    assert run(tmp_path, "--preflight", "--plan-file", str(plan), "--agent-root", str(agent_root), "--state-root", str(state_root), "--candidate", candidates[0], "--candidate", candidates[1]).returncode == 0
    quarantine = state_root / "staging-quarantine"
    quarantine.mkdir()
    os.rename(candidates[0], quarantine / Path(candidates[0]).name)
    result = run(tmp_path, "--apply", "--confirm", "--plan-file", str(plan), "--agent-root", str(agent_root), "--state-root", str(state_root), "--quarantine-root", str(quarantine))
    assert result.returncode == 0, result.stderr
    assert not Path(candidates[1]).exists()
    second = run(tmp_path, "--apply", "--confirm", "--plan-file", str(plan), "--agent-root", str(agent_root), "--state-root", str(state_root), "--quarantine-root", str(quarantine))
    assert second.returncode == 0, second.stderr
    events = [json.loads(line)["event"] for line in (quarantine / "audit.log").read_text().splitlines()]
    assert "resume_verified" in events and events.count("quarantined") == 1


def test_identity_or_symlink_is_rejected(tmp_path):
    agent_root, state_root, candidates = fixture(tmp_path)
    (Path(candidates[0]) / ".release-identity").write_text("{}")
    plan = tmp_path / "plan.json"
    result = run(tmp_path, "--preflight", "--plan-file", str(plan), "--agent-root", str(agent_root), "--state-root", str(state_root), "--candidate", candidates[0])
    assert result.returncode != 0
    assert "Legacy-Staging" in result.stderr or "Identität" in result.stderr
