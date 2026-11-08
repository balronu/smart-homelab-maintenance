#!/usr/bin/env bash
set -Eeuo pipefail

# Installs only the fixed root-side helper contract. It never discovers or
# authorizes a guest implicitly: the initial allowlist is empty unless an
# already existing, verified allowlist is preserved.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/agent-common.sh"

readonly HELPER_ROOT="/usr/libexec/${AGENT_NAME}"
readonly HELPER_PATH="$HELPER_ROOT/lxc-apt-helper"
readonly HELPER_UNIT="/etc/systemd/system/${AGENT_NAME}-lxc-helper.service"
readonly DISCOVERY_PATH="$HELPER_ROOT/lxc-discovery.py"
readonly DISCOVERY_UNIT="/etc/systemd/system/${AGENT_NAME}-lxc-discovery.service"
readonly HELPER_ETC="$ETC_ROOT/lxc-apt-allowlist.toml"
readonly ROLLBACK_ROOT="/var/lib/${AGENT_NAME}/helper-rollback"

source_dir=""
expected_commit=""
apply=0
start=0

usage() {
    cat <<'EOF'
Verwendung:
  install-lxc-helper.sh --source-dir DIR --expected-commit SHA [--apply [--start]]

Ohne --apply wird nur geprüft. --apply installiert den unveränderten Helper,
die Unit und eine leere root-owned Allowlist, falls noch keine existiert.
Der Dienst wird nur mit zusätzlichem --start gestartet. Das Skript aktiviert
keine neuen Gastberechtigungen und erzeugt keine Wildcards.
EOF
}

while (($#)); do
    case "$1" in
        --source-dir) source_dir="${2:?Wert für --source-dir fehlt}"; shift 2 ;;
        --expected-commit) expected_commit="${2:?Wert für --expected-commit fehlt}"; shift 2 ;;
        --apply) apply=1; shift ;;
        --start) start=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "Unbekannte Option: $1" ;;
    esac
done

require_root
require_command git
require_command install
require_command sha256sum
require_command stat
require_command systemctl
[[ -n "$source_dir" ]] || { usage >&2; die "--source-dir fehlt."; }
validate_source "$source_dir"
verify_commit "$source_dir" "$expected_commit"
[[ -f "$source_dir/scripts/smh-lxc-apt-helper.py" ]] || die "Helper-Quelle fehlt."
[[ -f "$source_dir/scripts/smart-homelab-maintenance-lxc-helper.service" ]] || die "Helper-Unit fehlt."
[[ -f "$source_dir/scripts/smh-lxc-discovery.py" ]] || die "Discovery-Quelle fehlt."
[[ -f "$source_dir/scripts/smart-homelab-maintenance-lxc-discovery.service" ]] || die "Discovery-Unit fehlt."

if [[ "$start" -eq 1 && "$apply" -ne 1 ]]; then
    die "--start erfordert --apply."
fi
if [[ "$apply" -eq 1 && "$start" -eq 1 ]]; then
    systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null || die "Der Agent-Dienst muss vor Helper-Start installiert sein."
fi

for target in "$HELPER_PATH" "$HELPER_UNIT" "$DISCOVERY_PATH" "$DISCOVERY_UNIT" "$HELPER_ETC"; do
    if [[ -e "$target" && ! -f "$target" ]]; then
        die "Ziel ist keine reguläre Datei: $target"
    fi
    if [[ -L "$target" ]]; then
        die "Symlink-Ziel wird aus Sicherheitsgründen nicht überschrieben: $target"
    fi
done

if [[ -e "$HELPER_ETC" ]]; then
    mode="$(stat -c '%a' "$HELPER_ETC")"
    [[ "$(stat -c '%u' "$HELPER_ETC")" == "0" && "$mode" =~ ^(600|640|644)$ ]] || die "Bestehende Allowlist ist nicht root-owned/sicher modegeschützt."
fi

if [[ "$apply" -ne 1 ]]; then
    info "LXC-Helper-Preflight PASS: Quelle, Commit, Unit, Zielpfade und Allowlist-Grenze geprüft."
    info "Kein Helper, Socket, Dienst oder Berechtigungszustand wurde geändert."
    exit 0
fi

getent group "$SERVICE_USER" >/dev/null 2>&1 || die "Agent-Gruppe fehlt: $SERVICE_USER"
install -d -m 0755 -o root -g root "$HELPER_ROOT" "$ETC_ROOT"
install -d -m 0700 -o root -g root "$ROLLBACK_ROOT"

stage="$(mktemp -d "/tmp/${AGENT_NAME}-helper.XXXXXX")"
rollback="$ROLLBACK_ROOT/$(date -u +%Y%m%dT%H%M%SZ)"
cleanup() { rm -rf -- "$stage"; }
trap cleanup EXIT
install -m 0755 -o root -g root "$source_dir/scripts/smh-lxc-apt-helper.py" "$stage/helper"
install -m 0644 -o root -g root "$source_dir/scripts/smart-homelab-maintenance-lxc-helper.service" "$stage/unit"
install -m 0755 -o root -g root "$source_dir/scripts/smh-lxc-discovery.py" "$stage/discovery"
install -m 0644 -o root -g root "$source_dir/scripts/smart-homelab-maintenance-lxc-discovery.service" "$stage/discovery-unit"

if [[ ! -e "$HELPER_ETC" ]]; then
    printf '%s\n' '# Managed by the Smart Homelab Maintenance installer.' '# Empty by default; discovery never grants guest access.' > "$stage/allowlist"
    chmod 0600 "$stage/allowlist"
else
    install -m 0600 -o root -g root "$HELPER_ETC" "$stage/allowlist"
fi

if [[ -e "$HELPER_PATH" || -e "$HELPER_UNIT" || -e "$DISCOVERY_PATH" || -e "$DISCOVERY_UNIT" || -e "$HELPER_ETC" ]]; then
    install -d -m 0700 -o root -g root "$rollback"
    for pair in "$HELPER_PATH helper" "$HELPER_UNIT unit" "$DISCOVERY_PATH discovery" "$DISCOVERY_UNIT discovery-unit" "$HELPER_ETC allowlist"; do
        set -- $pair
        if [[ -f "$1" ]]; then install -m 0600 -o root -g root "$1" "$rollback/$2"; fi
    done
fi

install -m 0755 -o root -g root "$stage/helper" "$HELPER_PATH"
install -m 0644 -o root -g root "$stage/unit" "$HELPER_UNIT"
install -m 0755 -o root -g root "$stage/discovery" "$DISCOVERY_PATH"
install -m 0644 -o root -g root "$stage/discovery-unit" "$DISCOVERY_UNIT"
install -m 0600 -o root -g root "$stage/allowlist" "$HELPER_ETC"
systemctl daemon-reload

if [[ "$start" -eq 1 ]]; then
    systemctl start "${AGENT_NAME}-lxc-helper.service"
    systemctl is-active --quiet "${AGENT_NAME}-lxc-helper.service" || die "Helper-Healthcheck fehlgeschlagen; Rollback-Staging: $rollback"
fi

info "LXC-Helper installiert; Allowlist bleibt ohne automatische Gastfreigaben."
info "Rollback-Staging: $rollback"
