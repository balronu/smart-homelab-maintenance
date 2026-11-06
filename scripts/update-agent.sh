#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/agent-common.sh"

source_dir=""
expected_commit=""
apply=0
while (($#)); do
    case "$1" in
        --source-dir) source_dir="${2:?Wert für --source-dir fehlt}"; shift 2 ;;
        --expected-commit) expected_commit="${2:?Wert für --expected-commit fehlt}"; shift 2 ;;
        --apply) apply=1; shift ;;
        -h|--help) printf '%s\n' 'update-agent.sh --source-dir DIR --expected-commit SHA [--apply]'; exit 0 ;;
        *) die "Unbekannte Option: $1" ;;
    esac
done
require_root
require_command git
[[ -n "$source_dir" && -n "$expected_commit" ]] || die "Quelle und erwarteter Commit sind erforderlich."
validate_source "$source_dir"
verify_commit "$source_dir" "$expected_commit"
[[ -d "$AGENT_ROOT" ]] || die "Agent ist nicht installiert."
[[ ! -f "/etc/systemd/system/$SERVICE_NAME" ]] || true
if systemctl is-active --quiet "$SERVICE_NAME"; then
    die "Agent ist aktiv. Update verweigert; kein automatischer Stopp oder Neustart."
fi
if [[ "$apply" -ne 1 ]]; then
    info "Vorprüfung erfolgreich. Kein Update ausgeführt."
    exit 0
fi
copy_tree_without_git "$source_dir/agent" "$AGENT_ROOT/agent.next"
mv -T "$AGENT_ROOT/agent.next" "$AGENT_ROOT/agent"
systemctl daemon-reload
info "Agent-Dateien aktualisiert. Dienst bleibt gestoppt; kein automatischer Neustart."
