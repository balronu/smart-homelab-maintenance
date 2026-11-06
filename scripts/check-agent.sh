#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/agent-common.sh"
require_root
require_command systemctl
[[ -d "$AGENT_ROOT" ]] || die "Agent ist nicht installiert."
[[ -f "$ETC_ROOT/agent.crt" && -f "$ETC_ROOT/agent.key" ]] || die "TLS-Dateien fehlen."
[[ -f "$ETC_ROOT/api-token" ]] || die "Credential-Datei fehlt."
[[ "$(stat -c '%a' "$ETC_ROOT/api-token")" == "600" ]] || die "Credential-Datei ist nicht mit 600 geschützt."
systemctl cat "$SERVICE_NAME" >/dev/null 2>&1 || die "systemd-Unit fehlt."
systemctl is-enabled --quiet "$SERVICE_NAME" && info "WARNUNG: Dienst ist aktiviert." || info "Dienst ist nicht aktiviert."
systemctl is-active --quiet "$SERVICE_NAME" && info "WARNUNG: Dienst ist aktiv." || info "Dienst ist nicht aktiv."
info "Datei- und Dienstprüfung abgeschlossen; es wurde keine Netzwerk- oder Updateaktion ausgeführt."
