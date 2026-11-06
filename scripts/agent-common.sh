#!/usr/bin/env bash
set -Eeuo pipefail

readonly AGENT_NAME="smart-homelab-maintenance"
readonly AGENT_ROOT="/opt/${AGENT_NAME}"
readonly ETC_ROOT="/etc/${AGENT_NAME}"
readonly STATE_ROOT="/var/lib/${AGENT_NAME}"
readonly SERVICE_NAME="${AGENT_NAME}-agent.service"
readonly SERVICE_USER="${AGENT_NAME}"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }

require_root() { [[ "${EUID}" -eq 0 ]] || die "Dieses Skript benötigt root."; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "Benötigtes Programm fehlt: $1"; }

validate_source() {
    local source="$1"
    [[ -d "$source" ]] || die "Quellverzeichnis fehlt: $source"
    [[ "$source" != / && "$source" != "$AGENT_ROOT"* ]] || die "Unsicheres Quellverzeichnis."
    [[ -f "$source/agent/smart_homelab_maintenance/server.py" ]] || die "Agent-Quellpaket fehlt."
    [[ -f "$source/custom_components/smart_homelab_maintenance/manifest.json" ]] || die "HA-Integration fehlt."
    [[ -f "$source/deploy/systemd/smart-homelab-maintenance-agent.service.example" ]] || die "systemd-Vorlage fehlt."
}

validate_private_host() {
    local host="$1"
    if python3 - "$host" <<'PY'
import ipaddress
import re
import sys

value = sys.argv[1].strip().rstrip(".")
try:
    address = ipaddress.ip_address(value)
except ValueError:
    if (
        not re.fullmatch(r"[A-Za-z0-9.-]+", value)
        or value.startswith(".")
        or value.endswith(".")
        or ".." in value
        or not value.endswith((".home.arpa", ".lan", ".local"))
    ):
        raise SystemExit(1)
else:
    if not (address.is_private or address.is_loopback or address.is_link_local):
        raise SystemExit(1)
PY
    then
        :
    else
        die "Agent-Host muss eine private IP-Adresse oder private DNS-Adresse sein."
    fi
}

verify_commit() {
    local source="$1" expected="$2"
    [[ -n "$expected" ]] || die "--expected-commit ist erforderlich."
    [[ "$expected" =~ ^[0-9a-f]{40}$ ]] || die "Ungültiger Commit-SHA."
    git -C "$source" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "Quelle muss ein Git-Arbeitsbaum sein."
    local actual
    actual="$(git -C "$source" rev-parse HEAD)"
    [[ "$actual" == "$expected" ]] || die "Quell-Commit stimmt nicht überein: $actual"
    git -C "$source" diff --quiet || die "Quell-Arbeitsbaum enthält uncommittete Änderungen."
}

check_certificate() {
    local cert="$1" key="$2" expected_host="$3"
    [[ -r "$cert" && -f "$cert" ]] || die "TLS-Zertifikat fehlt oder ist nicht lesbar."
    [[ -r "$key" && -f "$key" ]] || die "TLS-Privatschlüssel fehlt oder ist nicht lesbar."
    require_command openssl
    openssl x509 -in "$cert" -noout -checkend 86400 >/dev/null || die "TLS-Zertifikat ist ungültig oder läuft in weniger als 24 Stunden ab."
    if [[ "$expected_host" == *:* || "$expected_host" =~ ^[0-9]+(\.[0-9]+){3}$ ]]; then
        openssl x509 -in "$cert" -noout -checkip "$expected_host" >/dev/null || die "TLS-Zertifikat enthält keinen passenden IP-SAN."
    else
        openssl x509 -in "$cert" -noout -checkhost "$expected_host" >/dev/null || die "TLS-Zertifikat enthält keinen passenden Hostnamen-SAN."
    fi
    local cert_key private_key
    cert_key="$(openssl x509 -in "$cert" -pubkey -noout | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')" || die "Zertifikat konnte nicht geprüft werden."
    private_key="$(openssl pkey -in "$key" -pubout 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')" || die "Privatschlüssel konnte nicht geprüft werden."
    [[ "$cert_key" == "$private_key" ]] || die "TLS-Zertifikat und Privatschlüssel gehören nicht zusammen."
}

ensure_token() {
    local path="$1"
    umask 077
    if [[ -e "$path" ]]; then
        [[ -f "$path" ]] || die "Credential-Pfad ist keine Datei."
        [[ "$(stat -c '%a' "$path")" == "600" ]] || die "Credential-Datei muss Modus 600 haben."
        [[ -s "$path" ]] || die "Credential-Datei ist leer."
        return
    fi
    install -d -m 0750 -o root -g root "$(dirname "$path")"
    python3 - "$path" <<'PY'
import secrets
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(secrets.token_urlsafe(48) + "\n", encoding="utf-8")
path.chmod(0o600)
PY
}

copy_tree_without_git() {
    local source="$1" target="$2"
    install -d -m 0755 "$target"
    find "$source" -mindepth 1 -maxdepth 1 ! -name .git -exec cp -a {} "$target/" \;
    [[ ! -e "$target/.git" ]] || die "Git-Metadaten dürfen nicht installiert werden."
}
