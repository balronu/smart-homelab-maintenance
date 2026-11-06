#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=agent-common.sh
source "$SCRIPT_DIR/agent-common.sh"

source_dir=""
expected_commit=""
cert_file=""
key_file=""
agent_host=""
agent_port="48128"
proxmox_url=""
proxmox_node=""
proxmox_ca=""
proxmox_token_file=""
apply=0

usage() {
    cat <<'EOF'
Verwendung:
  install-agent.sh --source-dir DIR --expected-commit SHA \
    --cert FILE --key FILE --agent-host NAME --proxmox-url URL \
    --proxmox-node NAME --proxmox-ca FILE --proxmox-token-file FILE \
    [--port PORT] [--apply]

Ohne --apply wird ausschließlich geprüft. --apply installiert Dateien, legt
den Dienst ab, führt aber weder enable noch start aus.
EOF
}

while (($#)); do
    case "$1" in
        --source-dir) source_dir="${2:?Wert für --source-dir fehlt}"; shift 2 ;;
        --expected-commit) expected_commit="${2:?Wert für --expected-commit fehlt}"; shift 2 ;;
        --cert) cert_file="${2:?Wert für --cert fehlt}"; shift 2 ;;
        --key) key_file="${2:?Wert für --key fehlt}"; shift 2 ;;
        --agent-host) agent_host="${2:?Wert für --agent-host fehlt}"; shift 2 ;;
        --port) agent_port="${2:?Wert für --port fehlt}"; shift 2 ;;
        --proxmox-url) proxmox_url="${2:?Wert für --proxmox-url fehlt}"; shift 2 ;;
        --proxmox-node) proxmox_node="${2:?Wert für --proxmox-node fehlt}"; shift 2 ;;
        --proxmox-ca) proxmox_ca="${2:?Wert für --proxmox-ca fehlt}"; shift 2 ;;
        --proxmox-token-file) proxmox_token_file="${2:?Wert für --proxmox-token-file fehlt}"; shift 2 ;;
        --apply) apply=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "Unbekannte Option: $1" ;;
    esac
done

require_root
require_command git
require_command python3
require_command systemctl
require_command pveversion
python3 -m venv --help >/dev/null 2>&1 || die "python3-venv fehlt."
[[ -n "$source_dir" && -n "$cert_file" && -n "$key_file" && -n "$agent_host" && -n "$proxmox_url" && -n "$proxmox_node" && -n "$proxmox_ca" && -n "$proxmox_token_file" ]] || { usage >&2; die "Pflichtoption fehlt."; }
[[ "$agent_port" =~ ^[0-9]+$ && "$agent_port" -ge 1024 && "$agent_port" -le 65535 ]] || die "Ungültiger unprivilegierter Port."
validate_private_host "$agent_host"
[[ "$proxmox_url" == https://* && "$proxmox_url" != *\?* && "$proxmox_url" != *\#* ]] || die "Proxmox-URL muss HTTPS ohne Query/Fragment verwenden."
[[ "$proxmox_url" != *'@'* ]] || die "Proxmox-URL darf keine eingebetteten Zugangsdaten enthalten."
[[ "$proxmox_node" =~ ^[A-Za-z0-9.-]+$ ]] || die "Ungültiger Proxmox-Knotenname."
[[ -r "$proxmox_ca" && -f "$proxmox_ca" ]] || die "Proxmox-CA fehlt oder ist nicht lesbar."
[[ -r "$proxmox_token_file" && -f "$proxmox_token_file" ]] || die "Proxmox-Credential fehlt oder ist nicht lesbar."
[[ "$(stat -c '%a' "$proxmox_token_file")" == "600" ]] || die "Proxmox-Credential muss Modus 600 haben."
[[ -s "$proxmox_token_file" ]] || die "Proxmox-Credential ist leer."
validate_source "$source_dir"
verify_commit "$source_dir" "$expected_commit"
check_certificate "$cert_file" "$key_file"

if [[ "$apply" -ne 1 ]]; then
    info "Vorprüfung erfolgreich. Kein Installationsschritt ausgeführt."
    info "TLS-Zertifikat, Quell-Commit, private DNS-Zone und Update-Sperre sind plausibel."
    exit 0
fi

[[ ! -e "$AGENT_ROOT" || -d "$AGENT_ROOT" ]] || die "Agent-Ziel ist kein Verzeichnis."
[[ ! -e "/etc/systemd/system/$SERVICE_NAME" ]] || die "Dienstdatei existiert bereits; update-agent.sh verwenden."
[[ ! -e "$STATE_ROOT" ]] || [[ -d "$STATE_ROOT" ]] || die "Zustandsziel ist kein Verzeichnis."

if ! getent group "$SERVICE_USER" >/dev/null 2>&1; then
    groupadd --system "$SERVICE_USER"
fi
if ! getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --gid "$SERVICE_USER" --home-dir "$AGENT_ROOT" --shell /usr/sbin/nologin "$SERVICE_USER"
fi
install -d -m 0755 -o root -g root "$AGENT_ROOT" "$ETC_ROOT"
install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$STATE_ROOT"
python3 -m venv "$AGENT_ROOT/venv"
copy_tree_without_git "$source_dir/agent" "$AGENT_ROOT/agent"
install -m 0644 -o root -g root "$source_dir/deploy/systemd/smart-homelab-maintenance-agent.service.example" "/etc/systemd/system/$SERVICE_NAME"
python3 - "$ETC_ROOT/agent.toml" "$agent_host" "$agent_port" "$proxmox_url" "$proxmox_node" <<'PY'
import sys
import json
from pathlib import Path

target = Path(sys.argv[1])
host, port, proxmox_url, proxmox_node = sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
target.write_text(
    f"listen_host = {json.dumps(host)}\n"
    f"listen_port = {port}\n"
    "api_version = \"1\"\n"
    "state_directory = \"/var/lib/smart-homelab-maintenance\"\n"
    "execution_enabled = false\n"
    "certificate = \"/etc/smart-homelab-maintenance/agent.crt\"\n"
    "private_key = \"/etc/smart-homelab-maintenance/agent.key\"\n"
    f"proxmox_url = {json.dumps(proxmox_url)}\n"
    f"proxmox_node = {json.dumps(proxmox_node)}\n"
    "proxmox_ca_file = \"/etc/smart-homelab-maintenance/proxmox-ca.crt\"\n",
    encoding="utf-8",
)
target.chmod(0o640)
PY
install -m 0644 -o root -g root "$cert_file" "$ETC_ROOT/agent.crt"
install -m 0640 -o root -g "$SERVICE_USER" "$key_file" "$ETC_ROOT/agent.key"
install -m 0644 -o root -g root "$proxmox_ca" "$ETC_ROOT/proxmox-ca.crt"
install -m 0600 -o root -g root "$proxmox_token_file" "$ETC_ROOT/proxmox-api-token"
ensure_token "$ETC_ROOT/api-token"
systemctl daemon-reload

info "Dateien installiert; Dienst bleibt absichtlich deaktiviert und gestoppt."
info "Vor einem Start müssen Server-Runtime, Proxmox-Client, CA/DNS und HA-Tests separat freigegeben sein."
