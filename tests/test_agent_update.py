from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_upgrade_process_requires_explicit_confirmation_and_healthcheck():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert "--apply" in script and "--confirm" in script
    assert "--expected-commit" in script and "--health-url" in script
    assert "--cacert" in script and "api_contract" in script
    assert "systemctl stop \"$SERVICE_NAME\"" in script
    assert "systemctl start \"$SERVICE_NAME\"" in script


def test_update_transaction_has_interrupted_swap_recovery():
    script = (ROOT / "scripts" / "update-agent.sh").read_text(encoding="utf-8")
    assert "agent.previous.$$.staging" in script
    assert "trap rollback ERR" in script
    assert 'mv -T "$AGENT_ROOT/agent" "$previous_dir"' in script
    assert 'mv -T "$next_dir" "$AGENT_ROOT/agent"' in script


def test_upgrade_help_is_non_mutating():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert "-h|--help) usage; exit 0" in script
    assert "--apply" in script
    assert "--confirm" in script
