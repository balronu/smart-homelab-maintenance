from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("lxc_helper_preflight", ROOT / "scripts" / "lxc-helper-preflight.py")
assert SPEC and SPEC.loader
preflight_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight_module)


def test_preflight_schema_is_fail_closed_for_wrong_commit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(preflight_module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(preflight_module, "TARGETS", (tmp_path / "allowlist.toml",))

    def runner(argv, **_kwargs):
        if argv[:4] == ["git", "-C", str(tmp_path), "rev-parse"]:
            return type("Result", (), {"returncode": 0, "stdout": "0" * 40, "stderr": ""})()
        return type("Result", (), {"returncode": 0, "stdout": "running\n", "stderr": ""})()

    result = preflight_module.preflight(tmp_path, "1" * 40, runner=runner)
    assert result["decision"] == "NO-GO"
    assert result["mutations_performed"] is False
    assert "source_commit" in result["failed_checks"]


def test_preflight_requires_explicit_apply_even_on_go(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(preflight_module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(preflight_module, "TARGETS", (tmp_path / "allowlist.toml",))
    for relative in preflight_module.REQUIRED_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")

    def runner(argv, **_kwargs):
        if argv[0] == "git" and argv[-1] == "HEAD":
            return type("Result", (), {"returncode": 0, "stdout": "a" * 40 + "\n", "stderr": ""})()
        return type("Result", (), {"returncode": 0, "stdout": "running\n", "stderr": ""})()

    result = preflight_module.preflight(tmp_path, "a" * 40, runner=runner)
    assert result["decision"] == "GO"
    assert result["apply_authorization_required"] is True
    assert result["mutations_performed"] is False
