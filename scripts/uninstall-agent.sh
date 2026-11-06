#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/agent-common.sh"

apply=0
confirm=""
while (($#)); do
    case "$1" in
        --apply) apply=1; shift ;;
        --confirm) confirm="${2:?Wert für --confirm fehlt}"; shift 2 ;;
        -h|--help) printf '%s\n' 'uninstall-agent.sh --confirm smart-homelab-maintenance [--apply]'; exit 0 ;;
        *) die "Unbekannte Option: $1" ;;
    esac
done
require_root
[[ "$confirm" == "$AGENT_NAME" ]] || die "Explizite Bestätigung fehlt."
[[ "$apply" -eq 1 ]] || { info "Vorprüfung erfolgreich. Keine Dateien entfernt."; exit 0; }
if systemctl is-active --quiet "$SERVICE_NAME"; then
    die "Dienst ist aktiv; kein automatischer Stopp oder Neustart."
fi
systemctl disable "$SERVICE_NAME" >/dev/null 2>&1 || true
rm -f "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
rm -rf -- "$AGENT_ROOT" "$ETC_ROOT"
info "Agent-Code, Unit und Konfiguration entfernt. Zustandsverzeichnis $STATE_ROOT wurde bewusst erhalten."
