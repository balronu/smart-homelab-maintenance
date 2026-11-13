import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "legacy_rollback_evidence.py"
SPEC = importlib.util.spec_from_file_location("legacy_rollback_evidence", SCRIPT)
EVIDENCE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EVIDENCE)


def agent_tree(tmp_path: Path) -> Path:
    root = tmp_path / "agent"
    (root / "smart_homelab_maintenance").mkdir(parents=True)
    (root / "smart_homelab_maintenance" / "__init__.py").write_text("__version__ = '1.0.6'\n")
    (root / "smart_homelab_maintenance" / "server.py").write_text("legacy\n")
    return root


def test_legacy_tree_gets_content_bound_proof_without_release_identity(tmp_path):
    root = agent_tree(tmp_path)
    evidence = EVIDENCE.create(root)
    assert evidence["release_identity"] is None
    assert "release_version" not in evidence
    assert EVIDENCE.verify(root) == evidence["tree_sha256"]


def test_legacy_proof_survives_two_sequential_upgrade_boundaries(tmp_path):
    root = agent_tree(tmp_path)
    EVIDENCE.create(root)
    first_rollback = tmp_path / "agent.previous.1.staging"
    root.rename(first_rollback)
    active = agent_tree(tmp_path / "next")
    (active / ".release-identity").write_text('{"schema": 1}\n')
    active.rename(root)
    assert EVIDENCE.verify(first_rollback)
    second_rollback = tmp_path / "agent.previous.2.staging"
    root.rename(second_rollback)
    next_active = agent_tree(tmp_path / "next2")
    (next_active / ".release-identity").write_text('{"schema": 1}\n')
    next_active.rename(root)
    assert EVIDENCE.verify(first_rollback)
    assert not (second_rollback / EVIDENCE.EVIDENCE_NAME).exists()


def test_tampered_legacy_tree_is_rejected(tmp_path):
    root = agent_tree(tmp_path)
    EVIDENCE.create(root)
    (root / "smart_homelab_maintenance" / "server.py").write_text("tampered\n")
    with pytest.raises(ValueError, match="Manifest"):
        EVIDENCE.verify(root)


def test_tampered_legacy_evidence_is_rejected(tmp_path):
    root = agent_tree(tmp_path)
    EVIDENCE.create(root)
    evidence = root / EVIDENCE.EVIDENCE_NAME
    evidence.write_text(evidence.read_text().replace('"release_identity": null', '"release_identity": "1.0.6"'))
    with pytest.raises(ValueError, match="fail-closed"):
        EVIDENCE.verify(root)


def test_symlink_and_release_identity_are_rejected(tmp_path):
    root = agent_tree(tmp_path)
    (root / "link").symlink_to(root / "smart_homelab_maintenance" / "server.py")
    with pytest.raises(ValueError, match="Symlink"):
        EVIDENCE.create(root)
    root = agent_tree(tmp_path / "identity")
    (root / ".release-identity").write_text("{}\n")
    with pytest.raises(ValueError, match="Release-Identität"):
        EVIDENCE.create(root)
