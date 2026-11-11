#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/agent-common.sh"

readonly READINESS_TIMEOUT_SECONDS=30
readonly READINESS_INTERVAL_SECONDS=1
readonly READINESS_FAILURE_EXIT=72
readonly ROLLBACK_FAILURE_EXIT=73
readonly AGENT_PORT=48128

source_dir=""
expected_commit=""
health_url=""
ca_file=""
apply=0
confirm=0
recover_staging=""
quarantine_root="$STATE_ROOT/staging-quarantine"
rollback_dir=""
previous_agent_version=""
expected_agent_version=""
update_started=0
recovery_running=0

usage() {
    cat <<'EOF'
Verwendung:
  upgrade-agent.sh --source-dir DIR --expected-commit SHA \
    --health-url https://PRIVATE/api/v1 --ca-file FILE [--apply --confirm]
  upgrade-agent.sh --recover-staging PATH [--quarantine-root DIR] [--confirm]

Ohne --apply bleibt der Dienst unverändert. --apply benötigt zusätzlich
--confirm, stoppt ausschließlich den Agent-Dienst, wartet begrenzt auf den
TLS-Healthcheck und stellt bei einem fehlgeschlagenen Healthcheck den
vorherigen Code wieder her. Rollback-Staging bleibt zur manuellen Prüfung
erhalten.

--recover-staging bleibt ohne --confirm rein lesend. Mit --confirm wird nur
ein zuvor positiv geprüftes, verwaistes Staging atomar in den Quarantänepfad
verschoben; Dateien werden nicht gelöscht oder überschrieben.
EOF
}

while (($#)); do
    case "$1" in
        --source-dir) source_dir="${2:?Wert für --source-dir fehlt}"; shift 2 ;;
        --expected-commit) expected_commit="${2:?Wert für --expected-commit fehlt}"; shift 2 ;;
        --health-url) health_url="${2:?Wert für --health-url fehlt}"; shift 2 ;;
        --ca-file) ca_file="${2:?Wert für --ca-file fehlt}"; shift 2 ;;
        --recover-staging) recover_staging="${2:?Staging-Pfad fehlt}"; shift 2 ;;
        --quarantine-root) quarantine_root="${2:?Quarantänepfad fehlt}"; shift 2 ;;
        --apply) apply=1; shift ;;
        --confirm) confirm=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "Unbekannte Option: $1" ;;
    esac
done

require_root
require_command git
require_command systemctl
require_command curl
require_command ss
require_command python3
if [[ -n "$recover_staging" ]]; then
    [[ "$apply" -eq 0 ]] || die "--recover-staging kann nicht mit --apply kombiniert werden."
    [[ "$recover_staging" = /* && "$quarantine_root" = /* ]] || die "Staging- und Quarantänepfad müssen absolut sein."
    canonical_state_root="$(realpath -e -- "$STATE_ROOT")" || die "State-Root ist nicht kanonisch auflösbar."
    [[ "$quarantine_root" == "$canonical_state_root"/* ]] || die "Quarantäne muss unter dem kanonischen State-Root liegen."
    [[ -d "$AGENT_ROOT/agent" ]] || die "Aktiver Agent fehlt; kein sicherer Wiederherstellungspfad."
    canonical_stage="$(realpath -e -- "$recover_staging")" || die "Staging-Pfad ist nicht kanonisch auflösbar."
    canonical_root="$(realpath -e -- "$AGENT_ROOT")" || die "Agent-Root ist nicht kanonisch auflösbar."
    [[ "$canonical_stage" == "$canonical_root"/agent.previous.*.staging ]] || die "Staging-Pfad liegt nicht als exaktes Rollback-Staging unter dem Agent-Root."
    [[ -d "$canonical_stage" && ! -L "$recover_staging" ]] || die "Staging-Pfad ist kein echtes Verzeichnis oder ein Symlink."
    [[ ! -e "$quarantine_root" || ! -L "$quarantine_root" ]] || die "Quarantänepfad darf kein Symlink sein."
    quarantine_parent="$(dirname -- "$quarantine_root")"
    canonical_quarantine_parent="$(realpath -e -- "$quarantine_parent")" || die "Quarantäne-Elternpfad ist nicht kanonisch auflösbar."
    [[ "$canonical_quarantine_parent" == "$canonical_state_root"/* || "$canonical_quarantine_parent" == "$canonical_state_root" ]] || die "Quarantäne-Elternpfad liegt nicht unter dem State-Root."
    quarantine_name="$(basename -- "$canonical_stage")"
    quarantine_root="$canonical_quarantine_parent/$(basename -- "$quarantine_root")"
    quarantine_target="$quarantine_root/$quarantine_name"
    [[ "$quarantine_target" != "$canonical_stage" ]] || die "Quarantäneziel darf nicht das Quellverzeichnis sein."
    [[ ! -e "$quarantine_target" ]] || die "Quarantäneziel existiert bereits; keine Überschreibung."

    staging_manifest() {
        python3 - "$1" <<'PY'
import hashlib
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for path in sorted(root.rglob("*")):
    rel = path.relative_to(root).as_posix()
    if path.is_symlink():
        raise SystemExit(f"Symlink im Staging: {rel}")
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"F {digest} {rel}")
    elif not path.is_dir():
        raise SystemExit(f"Nicht unterstützter Dateityp im Staging: {rel}")
print("\n".join(rows))
PY
    }

    staging_process_check() {
        python3 - "$canonical_stage" <<'PY'
import os
import sys
from pathlib import Path

target = os.path.realpath(sys.argv[1])
self_pid = os.getpid()
ancestor_pids = {self_pid}
cursor = self_pid
while cursor > 1:
    try:
        fields = (Path("/proc") / str(cursor) / "stat").read_text().split()
        cursor = int(fields[3])
    except (FileNotFoundError, PermissionError, OSError, ValueError, IndexError):
        break
    ancestor_pids.add(cursor)
bad = []
for entry in Path("/proc").iterdir():
    if not entry.name.isdigit() or int(entry.name) in ancestor_pids:
        continue
    pid = entry.name
    try:
        cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        refs = [os.path.realpath(entry / "cwd"), os.path.realpath(entry / "root")]
        refs += [os.path.realpath(fd) for fd in (entry / "fd").iterdir() if os.path.islink(fd)]
    except (PermissionError, FileNotFoundError, OSError):
        continue
    if any(ref == target or ref.startswith(target + os.sep) for ref in refs):
        bad.append(f"PID {pid} referenziert Staging: {cmd.strip()}")
    if any(word in cmd for word in ("upgrade-agent.sh", "update-agent.sh", "agent.failed.", "rollback")):
        bad.append(f"aktiver Upgrade/Rollback-Prozess PID {pid}: {cmd.strip()}")
if bad:
    raise SystemExit("; ".join(sorted(set(bad))))
PY
    }

    systemd_refs="$(grep -R -F -n -- "$canonical_stage" /etc/systemd/system /etc/systemd/system.d /etc/smart-homelab-maintenance 2>/dev/null || true)"
    [[ -z "$systemd_refs" ]] || die "Systemd-/Konfigurationsreferenz auf Staging gefunden: $systemd_refs"
    staging_process_check || die "Aktiver Upgrade-, Rollback- oder Dateireferenz-Prozess gefunden."
    manifest_before="$(mktemp)"
    active_manifest=""
    trap 'rm -f -- "$manifest_before" "$active_manifest" "${manifest_before}.after"' EXIT
    staging_manifest "$canonical_stage" > "$manifest_before" || die "Staging-Integrität konnte nicht erfasst werden."
    candidate_count=0
    for candidate in "$AGENT_ROOT"/agent.previous.*.staging; do
        [[ -d "$candidate" && ! -L "$candidate" && "$(realpath -e -- "$candidate")" != "$canonical_stage" ]] || continue
        staging_manifest "$candidate" >/dev/null || die "Alternativer Rollback-Kandidat ist nicht verwendbar: $candidate"
        candidate_count=$((candidate_count + 1))
    done
    (( candidate_count > 0 )) || die "Kein alternativer Rollback-Kandidat bleibt erhalten."
    active_manifest="$(mktemp)"
    staging_manifest "$AGENT_ROOT/agent" > "$active_manifest" || die "Aktiver Agent ist kein verwendbarer Wiederherstellungspfad."
    info "Staging-Recovery-Preflight positiv: $canonical_stage"
    info "Alternativer Rollback-Kandidaten: $candidate_count"
    if [[ "$confirm" -ne 1 ]]; then
        info "Keine Quarantäne ausgeführt; --confirm fehlt."
        exit 0
    fi
    [[ ! -e "$quarantine_root" || -d "$quarantine_root" ]] || die "Quarantänepfad ist kein Verzeichnis."
    install -d -m 0750 -o root -g root -- "$quarantine_root"
    [[ ! -e "$quarantine_target" ]] || die "Quarantäneziel existiert bereits; keine Überschreibung."
    mv -T -- "$canonical_stage" "$quarantine_target"
    staging_manifest "$quarantine_target" > "${manifest_before}.after" || die "Integritätsprüfung nach Quarantäne fehlgeschlagen."
    cmp -s "$manifest_before" "${manifest_before}.after" || die "Hash-/Strukturvergleich nach Quarantäne fehlgeschlagen."
    audit="$quarantine_root/audit.log"
    printf '%s staging_quarantine source=%s target=%s source_sha256=%s active_sha256=%s candidates=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$canonical_stage" "$quarantine_target" \
        "$(sha256sum "$manifest_before" | awk '{print $1}')" "$(sha256sum "$active_manifest" | awk '{print $1}')" "$candidate_count" >> "$audit"
    chmod 0640 -- "$audit"
    info "Staging in Quarantäne verschoben und Integrität verifiziert: $quarantine_target"
    exit 0
fi
[[ -n "$source_dir" && -n "$expected_commit" && -n "$health_url" && -n "$ca_file" ]] || { usage >&2; die "Pflichtoption fehlt."; }
[[ "$health_url" == https://* && "$health_url" != *\?* && "$health_url" != *\#* ]] || die "Health-URL muss HTTPS ohne Query/Fragment verwenden."
[[ -r "$ca_file" && -f "$ca_file" ]] || die "Healthcheck-CA fehlt oder ist nicht lesbar."
validate_source "$source_dir"
verify_commit "$source_dir" "$expected_commit"
[[ -d "$AGENT_ROOT" ]] || die "Agent ist nicht installiert."
systemctl cat "$SERVICE_NAME" >/dev/null 2>&1 || die "Agent-Dienst ist nicht installiert."

read_agent_version() {
    local package_root="$1"
    python3 - "$package_root/smart_homelab_maintenance/__init__.py" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r'^__version__\s*=\s*["\x27]([^"\x27]+)["\x27]\s*$', text, re.MULTILINE)
if not match:
    raise SystemExit("Agent-Version fehlt oder ist ungültig")
print(match.group(1))
PY
}

validate_health_payload() {
    local payload="$1" expected_version="$2"
    python3 - "$payload" "$expected_version" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
expected_version = sys.argv[2]
data = payload.get("data", {})
if payload.get("schema_version") != "1":
    raise SystemExit("schema_version ist inkompatibel")
if data.get("status") != "ok":
    raise SystemExit("Healthcheck meldet keinen OK-Status")
if data.get("agent_version") != expected_version:
    raise SystemExit("Healthcheck meldet eine unerwartete Agent-Version")
if data.get("api_contract") != "1.1":
    raise SystemExit("API-Vertrag ist inkompatibel")
PY
}

wait_for_health() {
    local expected_version="$1" baseline_restarts="${2:-}"
    local lifecycle_restarts="${3:-}" lifecycle_invocation="${4:-}" lifecycle_start="${5:-}"
    local deadline=$((SECONDS + READINESS_TIMEOUT_SECONDS))
    local payload=""
    local last_error="Dienst nicht bereit"
    local lifecycle_snapshot current_restarts current_invocation current_start
    while (( SECONDS < deadline )); do
        if [[ -n "$baseline_restarts" ]]; then
            if ! lifecycle_snapshot="$(read_lifecycle_snapshot)"; then
                printf 'ERROR: systemd-Lebenszyklusdaten sind während der Readiness unvollständig oder ungültig.\n' >&2
                return "$READINESS_FAILURE_EXIT"
            fi
            IFS=$'\t' read -r current_restarts current_invocation current_start <<<"$lifecycle_snapshot"
            if (( current_restarts > baseline_restarts )); then
                printf 'ERROR: systemd hat den Agent während der Readiness neu gestartet (NRestarts %s -> %s).\n' \
                    "$baseline_restarts" "$current_restarts" >&2
                return "$READINESS_FAILURE_EXIT"
            fi
            if [[ -n "$lifecycle_restarts" ]]; then
                if (( current_restarts != lifecycle_restarts )); then
                    printf 'ERROR: NRestarts hat sich nach dem kontrollierten Start verändert (%s -> %s); Neustart oder Zählerreset nicht eindeutig.\n' \
                        "$lifecycle_restarts" "$current_restarts" >&2
                    return "$READINESS_FAILURE_EXIT"
                fi
                if [[ "$current_invocation" != "$lifecycle_invocation" \
                    || "$current_start" != "$lifecycle_start" ]]; then
                    printf 'ERROR: systemd-Lebenszyklus hat sich während der Readiness geändert (InvocationID/Startzeitpunkt).\n' >&2
                    return "$READINESS_FAILURE_EXIT"
                fi
            fi
        fi
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            if payload="$(curl --fail --silent --show-error \
                --connect-timeout 2 --max-time 5 --cacert "$ca_file" \
                "$health_url/health" 2>/dev/null)"; then
                if validate_health_payload "$payload" "$expected_version" 2>/dev/null; then
                    if [[ -n "$baseline_restarts" ]]; then
                        if ! lifecycle_snapshot="$(read_lifecycle_snapshot)"; then
                            printf 'ERROR: systemd-Lebenszyklusdaten fehlen unmittelbar nach dem Healthcheck.\n' >&2
                            return "$READINESS_FAILURE_EXIT"
                        fi
                        IFS=$'\t' read -r current_restarts current_invocation current_start <<<"$lifecycle_snapshot"
                        if (( current_restarts > baseline_restarts )); then
                            printf 'ERROR: systemd hat den Agent unmittelbar nach dem Healthcheck neu gestartet (NRestarts %s -> %s).\n' \
                                "$baseline_restarts" "$current_restarts" >&2
                            return "$READINESS_FAILURE_EXIT"
                        fi
                        if [[ -n "$lifecycle_restarts" \
                            && ( "$current_restarts" != "$lifecycle_restarts" \
                                || "$current_invocation" != "$lifecycle_invocation" \
                                || "$current_start" != "$lifecycle_start" ) ]]; then
                            printf 'ERROR: systemd-Lebenszyklus oder NRestarts änderte sich unmittelbar nach dem Healthcheck.\n' >&2
                            return "$READINESS_FAILURE_EXIT"
                        fi
                    fi
                    return 0
                fi
                last_error="Healthcheck-Antwort ist inkompatibel"
            else
                last_error="TLS/HTTP-Healthcheck nicht erreichbar"
            fi
        else
            last_error="Dienst ist nicht aktiv"
        fi
        sleep "$READINESS_INTERVAL_SECONDS"
    done
    printf 'ERROR: Readiness-Timeout nach %ss: %s\n' "$READINESS_TIMEOUT_SECONDS" "$last_error" >&2
    return "$READINESS_FAILURE_EXIT"
}

read_lifecycle_snapshot() {
    local restarts invocation start
    restarts="$(systemctl show --property=NRestarts --value "$SERVICE_NAME" 2>/dev/null || true)"
    invocation="$(systemctl show --property=InvocationID --value "$SERVICE_NAME" 2>/dev/null || true)"
    start="$(systemctl show --property=ExecMainStartTimestampMonotonic --value "$SERVICE_NAME" 2>/dev/null || true)"
    [[ "$restarts" =~ ^[0-9]+$ ]] || return 1
    [[ "$invocation" =~ ^[0-9a-fA-F-]{16,}$ ]] || return 1
    [[ "$start" =~ ^[0-9]+$ && "$start" -gt 0 ]] || return 1
    printf '%s\t%s\t%s\n' "$restarts" "$invocation" "$start"
}

port_has_blocking_state() {
    local sockets
    sockets="$(ss -Htanp "sport = :$AGENT_PORT" 2>/dev/null || true)"
    [[ -n "$sockets" ]] || return 1
    # TIME-WAIT is a kernel-owned, terminal connection state. It has no
    # listener or process owner and is safe for this server's SO_REUSEADDR
    # bind. Every other state remains a safety block.
    awk '$1 != "TIME-WAIT" { found = 1 } END { exit(found ? 0 : 1) }' <<<"$sockets"
}

wait_for_port_free() {
    local deadline=$((SECONDS + 10))
    while (( SECONDS < deadline )); do
        if ! systemctl is-active --quiet "$SERVICE_NAME" \
            && ! port_has_blocking_state; then
            return 0
        fi
        sleep 0.25
    done
    printf 'ERROR: Dienst oder TCP-Zustand auf Port %s bleibt nach dem Dienststopp bestehen. Kein Startversuch ausgeführt.\n' "$AGENT_PORT" >&2
    return 1
}

port_forensics() {
    local phase="$1" control_group main_pid control_pid
    control_group="$(systemctl show --property=ControlGroup --value "$SERVICE_NAME" 2>/dev/null || true)"
    main_pid="$(systemctl show --property=MainPID --value "$SERVICE_NAME" 2>/dev/null || true)"
    control_pid="$(systemctl show --property=ControlPID --value "$SERVICE_NAME" 2>/dev/null || true)"
    info "Port-Diagnose ($phase): MainPID=$main_pid ControlPID=$control_pid ControlGroup=$control_group"
    ss -Htanp "sport = :$AGENT_PORT" 2>/dev/null || true
    if [[ -n "$control_group" && -r "/sys/fs/cgroup$control_group/cgroup.procs" ]]; then
        info "Cgroup-Prozesse ($phase): $(tr '\n' ' ' < "/sys/fs/cgroup$control_group/cgroup.procs")"
    fi
}

version_is_older() {
    python3 - "$1" "$2" <<'PY'
import re
import sys

def parse(value):
    beta = re.fullmatch(r"0\.1\.0-beta\.(\d+)", value)
    if beta:
        return (0, 1, 0, 0, int(beta.group(1)))
    stable = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if stable:
        return (1, int(stable.group(1)), int(stable.group(2)), int(stable.group(3)), 0)
    return None

candidate = parse(sys.argv[1])
current = parse(sys.argv[2])
if candidate is None or current is None:
    raise SystemExit(1)
raise SystemExit(0 if candidate < current else 1)
PY
}

check_historical_staging() {
    local dirs=() dir staged_version
    for dir in "$AGENT_ROOT"/agent.previous.*.staging; do
        [[ -d "$dir" ]] || continue
        dirs+=("$dir")
    done
    ((${#dirs[@]} == 0)) && return 0
    systemctl is-active --quiet "$SERVICE_NAME" || die "Rollback-Staging vorhanden, aber Agent-Dienst ist nicht aktiv. Manuelle Prüfung erforderlich."
    local current_version
    if ! current_version="$(read_agent_version "$AGENT_ROOT/agent")"; then
        die "Aktive Agent-Version ist bei vorhandenem Rollback-Staging nicht lesbar. Manuelle Prüfung erforderlich."
    fi
    for dir in "${dirs[@]}"; do
        if ! staged_version="$(read_agent_version "$dir")"; then
            die "Rollback-Staging enthält keine gültige Agent-Version. Manuelle Prüfung erforderlich."
        fi
        if [[ "$staged_version" == "$current_version" ]]; then
            if diff -qr --exclude='__pycache__' "$dir" "$AGENT_ROOT/agent" >/dev/null 2>&1; then
                info "Identisches Rollback-Staging bleibt erhalten: $dir ($staged_version)"
                continue
            fi
            die "Rollback-Staging ist gleich versioniert, aber inhaltlich abweichend ($staged_version). Manuelle Prüfung erforderlich."
        fi
        if ! version_is_older "$staged_version" "$current_version"; then
            die "Rollback-Staging ist nicht eindeutig historisch ($staged_version vs. $current_version). Manuelle Prüfung erforderlich."
        fi
        info "Historisches Rollback-Staging bleibt erhalten: $dir ($staged_version)"
    done
    if ! wait_for_health "$current_version"; then
        die "Aktiver Agent konnte bei vorhandenem Rollback-Staging nicht TLS-validiert bestätigt werden."
    fi
}

check_historical_staging

if [[ "$apply" -ne 1 ]]; then
    info "Vorprüfung erfolgreich. Quelle, Commit, Dienst, Health-URL, CA und historisches Rollback-Staging sind plausibel. Kein Update ausgeführt."
    exit 0
fi
[[ "$confirm" -eq 1 ]] || die "--apply benötigt die ausdrückliche Bestätigung --confirm."

recover() {
    local reason="$1"
    if (( recovery_running )); then
        return "$ROLLBACK_FAILURE_EXIT"
    fi
    recovery_running=1
    printf 'WARNUNG: Update fehlgeschlagen (%s); starte kontrollierten Rollback.\n' "$reason" >&2
    systemctl stop "$SERVICE_NAME" || true
    systemctl reset-failed "$SERVICE_NAME" || true
    if [[ -n "$rollback_dir" && -d "$rollback_dir" ]]; then
        local failed_dir="$AGENT_ROOT/agent.failed.$$.staging"
        if [[ -e "$failed_dir" ]]; then
            printf 'ERROR: Rollback-Ziel existiert bereits: %s\n' "$failed_dir" >&2
            return "$ROLLBACK_FAILURE_EXIT"
        fi
        mv -T "$AGENT_ROOT/agent" "$failed_dir" || return "$ROLLBACK_FAILURE_EXIT"
        mv -T "$rollback_dir" "$AGENT_ROOT/agent" || return "$ROLLBACK_FAILURE_EXIT"
        rollback_dir=""
        if [[ "$was_active" -eq 1 ]]; then
            systemctl start "$SERVICE_NAME" || return "$ROLLBACK_FAILURE_EXIT"
            if ! wait_for_health "$previous_agent_version"; then
                systemctl stop "$SERVICE_NAME" || true
                systemctl reset-failed "$SERVICE_NAME" || true
                printf 'ERROR: Rollback-Code wurde bereitgestellt, aber der Rollback-Healthcheck schlug fehl.\n' >&2
                return "$ROLLBACK_FAILURE_EXIT"
            fi
        fi
        printf 'Rollback erfolgreich; fehlerhafter Code bleibt unter %s erhalten.\n' "$failed_dir" >&2
        return 0
    fi
    if [[ "$was_active" -eq 1 ]]; then
        systemctl start "$SERVICE_NAME" || return "$ROLLBACK_FAILURE_EXIT"
    fi
    return 0
}

finish() {
    local rc="$?"
    trap - EXIT
    if (( rc != 0 && update_started )); then
        if ! recover "Exit-Code $rc"; then
            printf 'ERROR: Rollback nicht sicher abgeschlossen. Dienst bleibt gestoppt.\n' >&2
            exit "$ROLLBACK_FAILURE_EXIT"
        fi
    fi
    exit "$rc"
}

was_active=0
systemctl is-active --quiet "$SERVICE_NAME" && was_active=1 || true
[[ "$was_active" -eq 1 ]] || die "Agent-Dienst ist nicht aktiv; kein automatischer Start im Updatepfad."
previous_agent_version="$(read_agent_version "$AGENT_ROOT/agent")"
expected_agent_version="$(read_agent_version "$source_dir/agent")"
restart_count_before="$(systemctl show --property=NRestarts --value "$SERVICE_NAME" 2>/dev/null || true)"
[[ "$restart_count_before" =~ ^[0-9]+$ ]] || die "systemd-Restartzähler ist nicht lesbar; kein Update ausgeführt."
lifecycle_before="$(read_lifecycle_snapshot)" || die "systemd-Lebenszyklusdaten sind vor dem Update nicht lesbar; kein Update ausgeführt."
IFS=$'\t' read -r lifecycle_restarts_before lifecycle_invocation_before lifecycle_start_before <<<"$lifecycle_before"
[[ "$lifecycle_restarts_before" == "$restart_count_before" ]] || die "NRestarts-Baseline ist inkonsistent; kein Update ausgeführt."
update_started=1
trap finish EXIT

port_forensics "vor-stop"
systemctl stop "$SERVICE_NAME"
port_forensics "nach-stop"
if ! wait_for_port_free; then
    # Do not leave the productive service stopped when a stale listener makes
    # the transaction unsafe. No agent tree has been swapped at this point.
    systemctl start "$SERVICE_NAME" || true
    die "Portfreigabe vor dem Agent-Start nicht nachweisbar; Update abgebrochen."
fi
port_forensics "vor-swap"
bash "$SCRIPT_DIR/update-agent.sh" --source-dir "$source_dir" --expected-commit "$expected_commit" --apply --keep-rollback
for candidate_dir in "$AGENT_ROOT"/agent.previous.*.staging; do
    [[ -d "$candidate_dir" ]] || continue
    if [[ "$(read_agent_version "$candidate_dir")" == "$previous_agent_version" ]]; then
        [[ -z "$rollback_dir" ]] || die "Mehrere Rollback-Stände passen zur vorherigen Agent-Version. Manuelle Prüfung erforderlich."
        rollback_dir="$candidate_dir"
    fi
done
[[ -n "$rollback_dir" ]] || die "Rollback-Staging wurde nicht erzeugt."
if ! wait_for_port_free; then
    die "Portfreigabe vor dem neuen Agent-Start nicht nachweisbar; Rollback wird ausgeführt."
fi
systemctl start "$SERVICE_NAME"
port_forensics "nach-start"
lifecycle_after="$(read_lifecycle_snapshot)" || die "systemd-Lebenszyklusdaten nach dem Start sind nicht lesbar; Rollback wird ausgeführt."
IFS=$'\t' read -r lifecycle_restarts_after lifecycle_invocation_after lifecycle_start_after <<<"$lifecycle_after"
if (( lifecycle_restarts_after > restart_count_before )); then
    die "NRestarts stieg bereits beim neuen Start ($restart_count_before -> $lifecycle_restarts_after); Rollback wird ausgeführt."
fi
if [[ "$lifecycle_invocation_after" == "$lifecycle_invocation_before" \
    || "$lifecycle_start_after" == "$lifecycle_start_before" ]]; then
    die "Neuer systemd-Lebenszyklus ist nicht eindeutig nachgewiesen; Rollback wird ausgeführt."
fi
wait_for_health "$expected_agent_version" "$restart_count_before" \
    "$lifecycle_restarts_after" "$lifecycle_invocation_after" "$lifecycle_start_after" \
    || exit "$READINESS_FAILURE_EXIT"

trap - EXIT
info "Agent aktualisiert, Readiness/TLS-Healthcheck erfolgreich, Dienst läuft. Rollback-Staging bleibt erhalten: $rollback_dir"
exit 0
