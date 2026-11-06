#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/agent-firewall-common.sh"

parse_common "$@"
validate_inputs
detect_backend
check_interface_source
check_conflicting_marker
check_chain_safety "$AGENT_FIREWALL_CHAIN4"

if rule_exists iptables -S "$AGENT_FIREWALL_CHAIN4"; then
    info "IPv4-Chain existiert bereits; nur bekannte Regeln werden ergänzt."
else
    run_change iptables -N "$AGENT_FIREWALL_CHAIN4"
fi
if rule_exists ip6tables -S "$AGENT_FIREWALL_CHAIN6"; then
    info "IPv6-Chain existiert bereits; nur bekannte Regeln werden ergänzt."
else
    run_change ip6tables -N "$AGENT_FIREWALL_CHAIN6"
fi

if ! rule_exists iptables -C "$AGENT_FIREWALL_CHAIN4" -p tcp -s "$ha_ip" -d "$host_ip" --dport 48128 -m comment --comment "$AGENT_FIREWALL_ALLOW_MARK" -j ACCEPT; then
    run_change iptables -A "$AGENT_FIREWALL_CHAIN4" -p tcp -s "$ha_ip" -d "$host_ip" --dport 48128 -m comment --comment "$AGENT_FIREWALL_ALLOW_MARK" -j ACCEPT
fi
if ! rule_exists iptables -C "$AGENT_FIREWALL_CHAIN4" -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_DROP_MARK" -j DROP; then
    run_change iptables -A "$AGENT_FIREWALL_CHAIN4" -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_DROP_MARK" -j DROP
fi
if ! rule_exists ip6tables -C "$AGENT_FIREWALL_CHAIN6" -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_DROP_MARK" -j DROP; then
    run_change ip6tables -A "$AGENT_FIREWALL_CHAIN6" -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_DROP_MARK" -j DROP
fi

if ! rule_exists iptables -C INPUT -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_MARK" -j "$AGENT_FIREWALL_CHAIN4"; then
    run_change iptables -I INPUT 1 -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_MARK" -j "$AGENT_FIREWALL_CHAIN4"
fi
if ! rule_exists ip6tables -C INPUT -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_MARK" -j "$AGENT_FIREWALL_CHAIN6"; then
    run_change ip6tables -I INPUT 1 -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_MARK" -j "$AGENT_FIREWALL_CHAIN6"
fi

if (( apply_mode == 1 )); then
    info "Nur SHM-Agent-Regeln wurden angewendet; Persistenz ist separat freizugeben."
else
    info "DRY-RUN: keine Firewallregel wurde angewendet."
fi
