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
    python3 - "$ha_ip" "$host_ip" "$AGENT_FIREWALL_ALLOW_MARK" "$AGENT_FIREWALL_DROP_MARK" "$saved" <<'PY' || die "Abweichende eigene IPv4-Regel gefunden; manuell prüfen."
import ipaddress
import sys

expected_source = ipaddress.ip_address(sys.argv[1])
expected_destination = ipaddress.ip_address(sys.argv[2])
allow_marker = sys.argv[3]
drop_marker = sys.argv[4]
saved = sys.argv[5]


def field(tokens, option):
    try:
        return tokens[tokens.index(option) + 1]
    except (ValueError, IndexError):
        return None


def exact_host(value, expected):
    try:
        if "/" in value:
            interface = ipaddress.ip_interface(value)
            return interface.version == 4 and interface.network.prefixlen == 32 and interface.ip == expected
        return ipaddress.ip_address(value) == expected
    except ValueError:
        return False


allow_indices = []
drop_indices = []
for line in saved.splitlines():
    tokens = line.split()
    if len(tokens) < 2 or tokens[0] != "-A":
        continue
    chain = tokens[1]
    comment = field(tokens, "--comment")
    if comment == allow_marker:
        valid = (
            chain == "SHM_AGENT_48128_V4"
            and
            field(tokens, "-p") == "tcp"
            and field(tokens, "--dport") == "48128"
            and field(tokens, "-j") == "ACCEPT"
            and exact_host(field(tokens, "-s") or "", expected_source)
            and exact_host(field(tokens, "-d") or "", expected_destination)
        )
        if not valid:
            raise SystemExit(1)
        allow_indices.append(len(allow_indices) + len(drop_indices))
    elif comment == drop_marker:
        valid = (
            chain == "SHM_AGENT_48128_V4"
            and
            field(tokens, "-p") == "tcp"
            and field(tokens, "--dport") == "48128"
            and field(tokens, "-j") == "DROP"
            and field(tokens, "-s") is None
            and field(tokens, "-d") is None
        )
        if not valid:
            raise SystemExit(1)
        drop_indices.append(len(allow_indices) + len(drop_indices))

if len(allow_indices) > 1 or len(drop_indices) > 1:
    raise SystemExit(1)
if drop_indices and not allow_indices:
    raise SystemExit(1)
if allow_indices and drop_indices and allow_indices[0] > drop_indices[0]:
    raise SystemExit(1)
PY
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
