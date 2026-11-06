#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$SCRIPT_DIR/agent-firewall-common.sh"

parse_common "$@"
validate_inputs
detect_backend
check_interface_source
check_chain_safety "$AGENT_FIREWALL_CHAIN4"

if rule_exists iptables -C INPUT -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_MARK" -j "$AGENT_FIREWALL_CHAIN4"; then
    run_change iptables -D INPUT -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_MARK" -j "$AGENT_FIREWALL_CHAIN4"
fi
if rule_exists ip6tables -C INPUT -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_MARK" -j "$AGENT_FIREWALL_CHAIN6"; then
    run_change ip6tables -D INPUT -p tcp --dport 48128 -m comment --comment "$AGENT_FIREWALL_MARK" -j "$AGENT_FIREWALL_CHAIN6"
fi
if rule_exists iptables -S "$AGENT_FIREWALL_CHAIN4"; then
    run_change iptables -F "$AGENT_FIREWALL_CHAIN4"
    run_change iptables -X "$AGENT_FIREWALL_CHAIN4"
fi
if rule_exists ip6tables -S "$AGENT_FIREWALL_CHAIN6"; then
    run_change ip6tables -F "$AGENT_FIREWALL_CHAIN6"
    run_change ip6tables -X "$AGENT_FIREWALL_CHAIN6"
fi

if (( apply_mode == 1 )); then
    info "Nur SHM-Agent-Regeln wurden entfernt."
else
    info "DRY-RUN: keine Firewallregel wurde entfernt."
fi
