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

Ohne --apply bleibt der Dienst unverändert. --apply benötigt zusätzlich
--confirm, stoppt ausschließlich den Agent-Dienst, wartet begrenzt auf den
TLS-Healthcheck und stellt bei einem fehlgeschlagenen Healthcheck den
vorherigen Code wieder her. Rollback-Staging bleibt zur manuellen Prüfung
erhalten.
EOF
}

while (($#)); do
    case "$1" in
        --source-dir) source_dir="${2:?Wert für --source-dir fehlt}"; shift 2 ;;
        --expected-commit) expected_commit="${2:?Wert für --expected-commit fehlt}"; shift 2 ;;
        --health-url) health_url="${2:?Wert für --health-url fehlt}"; shift 2 ;;
        --ca-file) ca_file="${2:?Wert für --ca-file fehlt}"; shift 2 ;;
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
    local expected_version="$1"
    local deadline=$((SECONDS + READINESS_TIMEOUT_SECONDS))
    local payload=""
    local last_error="Dienst nicht bereit"
    while (( SECONDS < deadline )); do
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            if payload="$(curl --fail --silent --show-error \
                --connect-timeout 2 --max-time 5 --cacert "$ca_file" \
                "$health_url/health" 2>/dev/null)"; then
                if validate_health_payload "$payload" "$expected_version" 2>/dev/null; then
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

wait_for_port_free() {
    local deadline=$((SECONDS + 10))
    while (( SECONDS < deadline )); do
        if ! ss -Hln "sport = :$AGENT_PORT" | grep -q .; then
            return 0
        fi
        sleep 0.25
    done
    printf 'ERROR: Port %s bleibt nach dem Dienststopp belegt. Kein Startversuch ausgeführt.\n' "$AGENT_PORT" >&2
    return 1
}

version_is_older() {
    python3 - "$1" "$2" <<'PY'
import re
import sys

pattern = re.compile(r"^0\.1\.0-beta\.(\d+)$")
candidate = pattern.fullmatch(sys.argv[1])
current = pattern.fullmatch(sys.argv[2])
if not candidate or not current:
    raise SystemExit(1)
raise SystemExit(0 if int(candidate.group(1)) < int(current.group(1)) else 1)
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
update_started=1
trap finish EXIT

systemctl stop "$SERVICE_NAME"
if ! wait_for_port_free; then
    # Do not leave the productive service stopped when a stale listener makes
    # the transaction unsafe. No agent tree has been swapped at this point.
    systemctl start "$SERVICE_NAME" || true
    die "Portfreigabe vor dem Agent-Start nicht nachweisbar; Update abgebrochen."
fi
bash "$SCRIPT_DIR/update-agent.sh" --source-dir "$source_dir" --expected-commit "$expected_commit" --apply --keep-rollback
for candidate_dir in "$AGENT_ROOT"/agent.previous.*.staging; do
    [[ -d "$candidate_dir" ]] || continue
    if [[ "$(read_agent_version "$candidate_dir")" == "$previous_agent_version" ]]; then
        [[ -z "$rollback_dir" ]] || die "Mehrere Rollback-Stände passen zur vorherigen Agent-Version. Manuelle Prüfung erforderlich."
        rollback_dir="$candidate_dir"
    fi
done
[[ -n "$rollback_dir" ]] || die "Rollback-Staging wurde nicht erzeugt."
systemctl start "$SERVICE_NAME"
wait_for_health "$expected_agent_version" || exit "$READINESS_FAILURE_EXIT"

trap - EXIT
info "Agent aktualisiert, Readiness/TLS-Healthcheck erfolgreich, Dienst läuft. Rollback-Staging bleibt erhalten: $rollback_dir"
exit 0
