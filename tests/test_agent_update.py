from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_upgrade_process_requires_explicit_confirmation_and_healthcheck():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert "--apply" in script and "--confirm" in script
    assert "--expected-commit" in script and "--health-url" in script
    assert "--cacert" in script and "api_contract" in script
    assert "systemctl stop \"$SERVICE_NAME\"" in script
    assert "systemctl start \"$SERVICE_NAME\"" in script
    assert "--connect-timeout 2" in script
    assert "--max-time 5" in script
    assert "READINESS_TIMEOUT_SECONDS=30" in script
    assert "READINESS_FAILURE_EXIT=72" in script
    assert "wait_for_port_free" in script
    assert 'ss -Hln "sport = :$AGENT_PORT"' in script


def test_update_transaction_has_interrupted_swap_recovery():
    script = (ROOT / "scripts" / "update-agent.sh").read_text(encoding="utf-8")
    assert "agent.previous.$$.staging" in script
    assert "trap rollback ERR" in script
    assert 'mv -T "$AGENT_ROOT/agent" "$previous_dir"' in script
    assert 'mv -T "$next_dir" "$AGENT_ROOT/agent"' in script


def test_upgrade_recovers_from_explicit_exit_and_bounds_restart_race():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert "trap finish EXIT" in script
    assert "systemctl reset-failed \"$SERVICE_NAME\"" in script
    assert "wait_for_health \"$expected_agent_version\"" in script
    assert "agent.failed.$$.staging" in script
    assert "Rollback-Healthcheck" in script or "Rollback-Code wurde bereitgestellt" in script
    assert "trap recovery ERR" not in script


def test_upgrade_does_not_delete_existing_rollback_staging():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert '"$AGENT_ROOT"/agent.previous.*.staging' in script
    assert "version_is_older" in script
    assert "check_historical_staging" in script
    assert "Manuelle Prüfung erforderlich" in script
    assert 'rm -rf -- "$rollback_dir"' not in script
    assert "Rollback-Staging bleibt erhalten" in script


def test_historical_staging_requires_active_health_and_keeps_ambiguous_state_blocked():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert 'systemctl is-active --quiet "$SERVICE_NAME"' in script
    assert 'wait_for_health "$current_version"' in script
    assert "nicht eindeutig historisch" in script
    assert "Mehrere Rollback-Stände passen" in script


def test_readiness_requires_tls_contract_and_expected_version():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert '--cacert "$ca_file"' in script
    assert 'data.get("agent_version") != expected_version' in script
    assert 'data.get("api_contract") != "1.1"' in script
    assert 'data.get("status") != "ok"' in script


def test_upgrade_checks_port_before_swapping_agent_tree():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    stop = script.index('systemctl stop "$SERVICE_NAME"')
    swap = script.index('bash "$SCRIPT_DIR/update-agent.sh"')
    assert stop < script.index("wait_for_port_free", stop) < swap
    assert 'systemctl start "$SERVICE_NAME" || true' in script


def test_unit_bounds_stop_and_keeps_single_restart_owner():
    unit = (ROOT / "deploy/systemd/smart-homelab-maintenance-agent.service.example").read_text(encoding="utf-8")
    assert "TimeoutStopSec=30" in unit
    assert "Restart=on-failure" in unit
    assert "ExecStart=" in unit
    assert unit.count("ExecStart=") == 1


def test_upgrade_help_is_non_mutating():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert "-h|--help) usage; exit 0" in script
    assert "--apply" in script
    assert "--confirm" in script
