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
    assert 'ss -Htanp "sport = :$AGENT_PORT"' in script
    assert 'TIME-WAIT' in script
    assert "port_has_blocking_state" in script
    assert "port_forensics" in script


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


def test_readiness_rejects_systemd_restart_during_upgrade():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert 'systemctl show --property=NRestarts --value "$SERVICE_NAME"' in script
    assert 'restart_count_before=' in script
    assert 'wait_for_health "$expected_agent_version" "$restart_count_before"' in script
    assert "systemd hat den Agent während der Readiness neu gestartet" in script
    assert "systemd hat den Agent unmittelbar nach dem Healthcheck neu gestartet" in script
    assert script.count('systemctl show --property=NRestarts --value "$SERVICE_NAME"') >= 2


def test_readiness_models_counter_reset_and_new_unit_lifecycle():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert "InvocationID" in script
    assert "ExecMainStartTimestampMonotonic" in script
    assert "read_lifecycle_snapshot" in script
    assert "NRestarts-Baseline ist inkonsistent" in script
    assert "NRestarts hat sich nach dem kontrollierten Start verändert" in script
    assert "Neuer systemd-Lebenszyklus ist nicht eindeutig nachgewiesen" in script
    assert "lifecycle_restarts_after" in script
    assert "lifecycle_invocation_after" in script
    assert "lifecycle_start_after" in script


def test_readiness_rejects_missing_or_invalid_lifecycle_values():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert '[[ "$restarts" =~ ^[0-9]+$ ]] || return 1' in script
    assert '[[ "$invocation" =~ ^[0-9a-fA-F-]{16,}$ ]] || return 1' in script
    assert '[[ "$start" =~ ^[0-9]+$ && "$start" -gt 0 ]] || return 1' in script
    assert "systemd-Lebenszyklusdaten sind während der Readiness unvollständig" in script
    assert "systemd-Lebenszyklusdaten fehlen unmittelbar nach dem Healthcheck" in script


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


def test_historical_staging_version_comparison_supports_stable_agent_releases():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert 're.fullmatch(r"0\\.1\\.0-beta\\.(\\d+)", value)' in script
    assert 're.fullmatch(r"(\\d+)\\.(\\d+)\\.(\\d+)", value)' in script
    assert "candidate < current" in script


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
    assert 'systemctl is-active --quiet "$SERVICE_NAME"' in script[script.index("wait_for_port_free") :]
    assert script.count("wait_for_port_free") >= 3


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


def test_staging_recovery_requires_explicit_confirmation_and_isolated_quarantine():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert "--recover-staging" in script
    assert "--quarantine-root" in script
    assert 'recover_staging=""' in script
    assert '[[ "$apply" -eq 0 ]] || die "--recover-staging kann nicht mit --apply kombiniert werden."' in script
    assert "realpath -e" in script
    assert 'canonical_state_root="$(realpath -e -- "$STATE_ROOT")"' in script
    assert 'canonical_quarantine_parent="$(realpath -e -- "$quarantine_parent")"' in script
    assert "! -L \"$recover_staging\"" in script
    assert "staging_process_check" in script
    assert "ancestor_pids" in script
    assert "fields = (Path(\"/proc\") / str(cursor) / \"stat\").read_text().split()" in script
    assert "active_script = re.search" in script
    assert "active_rollback = re.search" in script
    assert "/etc/systemd/system" in script
    assert "Kein alternativer Rollback-Kandidat bleibt erhalten" in script
    assert '[[ "$confirm" -ne 1 ]]' in script
    assert 'mv -T -- "$canonical_stage" "$quarantine_target"' in script
    assert "cmp -s \"$manifest_before\"" in script
    assert '>> "$audit"' in script
    assert 'rm -rf' not in script


def test_staging_recovery_rejects_unsafe_paths_and_collision():
    script = (ROOT / "scripts" / "upgrade-agent.sh").read_text(encoding="utf-8")
    assert "Staging-Pfad liegt nicht als exaktes Rollback-Staging unter dem Agent-Root" in script
    assert "Staging-Pfad ist kein echtes Verzeichnis oder ein Symlink" in script
    assert "Quarantäneziel existiert bereits; keine Überschreibung" in script
    assert "Aktiver Upgrade-/Rollback- oder Dateireferenz-Prozess gefunden" in script or "Aktiver Upgrade-, Rollback- oder Dateireferenz-Prozess gefunden" in script
    assert "Symlink im Staging" in script
    assert "Hash-/Strukturvergleich nach Quarantäne fehlgeschlagen" in script
