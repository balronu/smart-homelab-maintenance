#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/agent-common.sh"

source_dir=""
expected_commit=""
health_url=""
ca_file=""
apply=0
confirm=0

usage() {
    cat <<'EOF'
Verwendung:
  upgrade-agent.sh --source-dir DIR --expected-commit SHA \
    --health-url https://PRIVATE/api/v1 --ca-file FILE [--apply --confirm]

Ohne --apply bleibt der Dienst unverändert. --apply benötigt zusätzlich
--confirm, stoppt ausschließlich den Agent-Dienst, prüft den Healthcheck und
stellt bei einem fehlgeschlagenen Healthcheck den vorherigen Code wieder her.
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
[[ -n "$source_dir" && -n "$expected_commit" && -n "$health_url" && -n "$ca_file" ]] || { usage >&2; die "Pflichtoption fehlt."; }
[[ "$health_url" == https://* && "$health_url" != *\?* && "$health_url" != *\#* ]] || die "Health-URL muss HTTPS ohne Query/Fragment verwenden."
[[ -r "$ca_file" && -f "$ca_file" ]] || die "Healthcheck-CA fehlt oder ist nicht lesbar."
validate_source "$source_dir"
verify_commit "$source_dir" "$expected_commit"
[[ -d "$AGENT_ROOT" ]] || die "Agent ist nicht installiert."
systemctl cat "$SERVICE_NAME" >/dev/null 2>&1 || die "Agent-Dienst ist nicht installiert."
compgen -G "$AGENT_ROOT/agent.previous.*.staging" >/dev/null && die "Altes Rollback-Staging ist vorhanden. Manuelle Prüfung erforderlich."

if [[ "$apply" -ne 1 ]]; then
    info "Vorprüfung erfolgreich. Quelle, Commit, Dienst, Health-URL und CA sind plausibel. Kein Update ausgeführt."
    exit 0
fi
[[ "$confirm" -eq 1 ]] || die "--apply benötigt die ausdrückliche Bestätigung --confirm."

was_active=0
systemctl is-active --quiet "$SERVICE_NAME" && was_active=1 || true
[[ "$was_active" -eq 1 ]] || die "Agent-Dienst ist nicht aktiv; kein automatischer Start im Updatepfad."
rollback_dir=""
recovery() {
    if [[ -n "$rollback_dir" && -d "$rollback_dir" ]]; then
        systemctl stop "$SERVICE_NAME" || true
        rm -rf -- "$AGENT_ROOT/agent.failed.$$"
        mv -T "$AGENT_ROOT/agent" "$AGENT_ROOT/agent.failed.$$" || true
        mv -T "$rollback_dir" "$AGENT_ROOT/agent" || true
        systemctl start "$SERVICE_NAME" || true
    else
        systemctl is-active --quiet "$SERVICE_NAME" || systemctl start "$SERVICE_NAME" || true
    fi
}
trap recovery ERR
systemctl stop "$SERVICE_NAME"
bash "$SCRIPT_DIR/update-agent.sh" --source-dir "$source_dir" --expected-commit "$expected_commit" --apply --keep-rollback
rollback_dir="$(find "$AGENT_ROOT" -maxdepth 1 -type d -name 'agent.previous.*.staging' -print -quit)"
[[ -n "$rollback_dir" ]] || die "Rollback-Staging wurde nicht erzeugt."
systemctl start "$SERVICE_NAME"
health_json="$(curl --fail --silent --show-error --max-time 10 --cacert "$ca_file" "$health_url/health")" || die "Agent-Healthcheck fehlgeschlagen."
python3 - "$health_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
data = payload.get("data", {})
if payload.get("schema_version") != "1" or not data.get("agent_version") or data.get("api_contract") != "1.1":
    raise SystemExit("Agent-Healthcheck meldet einen inkompatiblen Vertrag.")
PY
rm -rf -- "$rollback_dir"
rollback_dir=""
trap - ERR
info "Agent aktualisiert, Healthcheck erfolgreich, Dienst läuft."
