#!/usr/bin/env bash
set -Eeuo pipefail

readonly AGENT_FIREWALL_CHAIN4="SHM_AGENT_48128_V4"
readonly AGENT_FIREWALL_CHAIN6="SHM_AGENT_48128_V6"
readonly AGENT_FIREWALL_MARK="smart-homelab-maintenance-48128"
readonly AGENT_FIREWALL_ALLOW_MARK="smart-homelab-maintenance-48128-allow"
readonly AGENT_FIREWALL_DROP_MARK="smart-homelab-maintenance-48128-drop"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }

host_ip=""
ha_ip=""
interface="vmbr0"
config_file=""
apply_mode=0
confirm_mode=0

usage_common() {
    cat <<'EOF'
Optionen:
  --config FILE       geheimnisfreie KEY=VALUE-Konfiguration laden
  --host-ip ADDRESS   Proxmox-Hostadresse für den Agenten
  --ha-ip ADDRESS     IPv4-Adresse von Home Assistant VM 104
  --interface NAME    erwartete Bridge, standardmäßig vmbr0
  --dry-run            nur prüfen/anzeigen (Standard)
  --apply             Änderungen tatsächlich ausführen (standardmäßig Dry-Run)
  --confirm           zusätzliche Bestätigung für --apply
EOF
}

load_config() {
    local key value line
    [[ -r "$config_file" ]] || die "Konfigurationsdatei ist nicht lesbar."
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%%#*}"
        [[ -z "${line//[[:space:]]/}" ]] && continue
        [[ "$line" == *=* ]] || die "Ungültige Konfigurationszeile."
        key="${line%%=*}"; value="${line#*=}"
        key="${key//[[:space:]]/}"; value="${value//[[:space:]]/}"
        case "$key" in
            HOST_IP) host_ip="$value" ;;
            HA_IP) ha_ip="$value" ;;
            INTERFACE) interface="$value" ;;
            *) die "Unbekannter Konfigurationsschlüssel: $key" ;;
        esac
    done < "$config_file"
}

parse_common() {
    local arg
    for arg in "$@"; do
        if [[ "$arg" == --config=* ]]; then config_file="${arg#*=}"; fi
    done
    [[ -z "$config_file" ]] || load_config
    while (($#)); do
        case "$1" in
            --config=*) config_file="${1#*=}"; shift ;;
            --config) config_file="${2:?Wert für --config fehlt}"; load_config; shift 2 ;;
            --host-ip) host_ip="${2:?Wert für --host-ip fehlt}"; shift 2 ;;
            --ha-ip) ha_ip="${2:?Wert für --ha-ip fehlt}"; shift 2 ;;
            --interface) interface="${2:?Wert für --interface fehlt}"; shift 2 ;;
            --dry-run) apply_mode=0; shift ;;
            --apply) apply_mode=1; shift ;;
            --confirm) confirm_mode=1; shift ;;
            -h|--help) usage_common; exit 0 ;;
            *) die "Unbekannte Option: $1" ;;
        esac
    done
}

validate_ipv4() {
    python3 - "$1" <<'PY'
import ipaddress
import sys
value = sys.argv[1]
address = ipaddress.ip_address(value)
if address.version != 4 or address.is_unspecified or address.is_multicast:
    raise SystemExit(1)
PY
}

detect_backend() {
    command -v iptables >/dev/null || die "iptables fehlt."
    command -v ip6tables >/dev/null || die "ip6tables fehlt."
    command -v iptables-save >/dev/null || die "iptables-save fehlt."
    command -v ip6tables-save >/dev/null || die "ip6tables-save fehlt."
    command -v ip >/dev/null || die "ip fehlt."
    command -v pvesh >/dev/null || die "pvesh fehlt; Proxmox-Konfliktprüfung nicht möglich."
    [[ "$(iptables -V 2>&1)" == *"legacy"* ]] || die "Nur der geprüfte iptables-legacy-Backend wird akzeptiert."
    [[ "$(ip6tables -V 2>&1)" == *"legacy"* ]] || die "Nur der geprüfte ip6tables-legacy-Backend wird akzeptiert."
    local pve_options
    pve_options="$(pvesh get /cluster/firewall/options --output-format json 2>/dev/null)" || die "Proxmox-Firewallstatus konnte nicht geprüft werden."
    if python3 -c 'import json,sys; d=json.loads(sys.argv[1]); raise SystemExit(0 if d.get("enable") else 1)' "$pve_options"; then
        die "Proxmox-Firewall ist aktiviert; keine konkurrierende Regelverwaltung verwenden."
    fi
    [[ "$interface" =~ ^[A-Za-z0-9_.-]+$ ]] || die "Ungültiger Interface-Name."
    ip link show "$interface" >/dev/null 2>&1 || die "Interface ist nicht vorhanden: $interface"
}

validate_inputs() {
    [[ -n "$host_ip" && -n "$ha_ip" ]] || die "--host-ip und --ha-ip sind erforderlich."
    validate_ipv4 "$host_ip" || die "Ungültige Host-IPv4-Adresse."
    validate_ipv4 "$ha_ip" || die "Ungültige HA-IPv4-Adresse."
    [[ "$host_ip" != "$ha_ip" ]] || die "Host- und HA-Adresse müssen verschieden sein."
    if (( apply_mode == 1 && confirm_mode != 1 )); then
        die "--apply benötigt zusätzlich --confirm."
    fi
}

run_change() {
    if (( apply_mode == 1 )); then
        "$@"
    else
        printf '+ '; printf '%q ' "$@"; printf '\n'
    fi
}

rule_exists() { "$@" >/dev/null 2>&1; }

check_interface_source() {
    ip -4 addr show dev "$interface" | grep -Fq " ${host_ip}/" || die "Hostadresse liegt nicht auf $interface."
}

check_conflicting_marker() {
    local saved
    saved="$(iptables-save -t filter)"
    if grep -F -- "--comment $AGENT_FIREWALL_ALLOW_MARK" <<<"$saved" | grep -Fq -- "-s "; then
        grep -F -- "--comment $AGENT_FIREWALL_ALLOW_MARK" <<<"$saved" | grep -F -- "-s $ha_ip -d $host_ip" >/dev/null || die "Abweichende eigene IPv4-Regel gefunden; manuell prüfen."
    fi
    if grep -F -- "--comment $AGENT_FIREWALL_DROP_MARK" <<<"$saved" | grep -Fq -- "-d "; then
        grep -F -- "--comment $AGENT_FIREWALL_DROP_MARK" <<<"$saved" >/dev/null || die "Abweichende eigene Drop-Regel gefunden; manuell prüfen."
    fi
}

check_chain_safety() {
    local chain="$1" saved line
    saved="$(iptables-save -t filter)"
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        case "$line" in
            *"-A $chain "*)
                [[ "$line" == *"$AGENT_FIREWALL_ALLOW_MARK"* || "$line" == *"$AGENT_FIREWALL_DROP_MARK"* ]] || die "Unmarkierte Regel in eigener Chain gefunden: $chain"
                ;;
        esac
    done <<<"$saved"
    saved="$(ip6tables-save -t filter)"
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        case "$line" in
            *"-A $AGENT_FIREWALL_CHAIN6 "*)
                [[ "$line" == *"$AGENT_FIREWALL_DROP_MARK"* ]] || die "Unmarkierte Regel in eigener IPv6-Chain gefunden."
                ;;
        esac
    done <<<"$saved"
}
