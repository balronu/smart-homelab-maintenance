#!/usr/bin/env bash
set -Eeuo pipefail

# Local certificate lifecycle helper for the read-only agent.
# Mutating actions require both --apply and --confirm. This script never
# starts/restarts a service and never prints key or credential material.

ACTION="${1:-}"
if [[ -n "$ACTION" ]]; then shift; fi

ca_dir=""
output_dir=""
target_dir=""
candidate_cert=""
candidate_key=""
ip_address=""
days="825"
prefix="agent"
apply=0
confirm=0

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "Benötigtes Programm fehlt: $1"; }

usage() {
    cat <<'EOF'
Verwendung:
  tls-agent.sh init-ca --ca-dir DIR [--days N] [--apply --confirm]
  tls-agent.sh issue --ca-dir DIR --output-dir DIR --ip IP [--prefix NAME]
                      [--days N] [--apply --confirm]
  tls-agent.sh self-signed --output-dir DIR --ip IP [--prefix NAME]
                            [--days N] [--apply --confirm]
  tls-agent.sh verify --ca-dir DIR --cert FILE --key FILE --ip IP
  tls-agent.sh renew --ca-dir DIR --output-dir DIR --ip IP [--prefix NAME]
                      [--days N] [--apply --confirm]
  tls-agent.sh rotate --ca-dir DIR --cert FILE --key FILE --ip IP
                       --target-dir DIR [--apply --confirm]

Mutierende Aktionen benötigen beide Schalter. Es werden keine Dienste
gestartet oder neugestartet. Private Schlüssel und Token werden nie ausgegeben.
EOF
}

if [[ "$ACTION" == "-h" || "$ACTION" == "--help" ]]; then
    usage
    exit 0
fi

while (($#)); do
    case "$1" in
        --ca-dir) ca_dir="${2:?Wert für --ca-dir fehlt}"; shift 2 ;;
        --output-dir) output_dir="${2:?Wert für --output-dir fehlt}"; shift 2 ;;
        --target-dir) target_dir="${2:?Wert für --target-dir fehlt}"; shift 2 ;;
        --cert) candidate_cert="${2:?Wert für --cert fehlt}"; shift 2 ;;
        --key) candidate_key="${2:?Wert für --key fehlt}"; shift 2 ;;
        --ip) ip_address="${2:?Wert für --ip fehlt}"; shift 2 ;;
        --days) days="${2:?Wert für --days fehlt}"; shift 2 ;;
        --prefix) prefix="${2:?Wert für --prefix fehlt}"; shift 2 ;;
        --apply) apply=1; shift ;;
        --confirm) confirm=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "Unbekannte Option: $1" ;;
    esac
done

[[ -n "$ACTION" ]] || { usage >&2; exit 2; }
require_command openssl
require_command python3
[[ "$days" =~ ^[1-9][0-9]{0,3}$ ]] || die "Ungültige Zertifikatsdauer."
[[ "$prefix" =~ ^[A-Za-z0-9._-]+$ ]] || die "Ungültiger Dateipräfix."

validate_ip() {
    python3 - "$1" <<'PY'
import ipaddress
import sys

address = ipaddress.ip_address(sys.argv[1])
if not address.is_private:
    raise SystemExit("IP muss privat sein")
PY
}

require_absolute_dir() {
    local value="$1" label="$2"
    [[ "$value" = /* && "$value" != "/" ]] || die "$label muss ein nicht-root Absolutpfad sein."
}

require_apply() {
    [[ "$apply" -eq 1 && "$confirm" -eq 1 ]] || die "$ACTION benötigt --apply und --confirm."
}

verify_pair() {
    local cert="$1" key="$2" expected_ip="$3" ca="$4"
    [[ -r "$cert" && -f "$cert" ]] || die "Zertifikat fehlt oder ist nicht lesbar."
    [[ -r "$key" && -f "$key" ]] || die "Privatschlüssel fehlt oder ist nicht lesbar."
    [[ -r "$ca" && -f "$ca" ]] || die "CA-Zertifikat fehlt oder ist nicht lesbar."
    openssl x509 -in "$cert" -noout -checkend 86400 >/dev/null || die "Zertifikat ist ungültig oder läuft in weniger als 24 Stunden ab."
    openssl verify -CAfile "$ca" "$cert" >/dev/null || die "Zertifikatskette ist nicht vertrauenswürdig."
    openssl x509 -in "$cert" -noout -checkip "$expected_ip" >/dev/null || die "Zertifikat enthält keinen passenden IP-SAN."
    local cert_key private_key
    cert_key="$(openssl x509 -in "$cert" -pubkey -noout | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')" || die "Zertifikat konnte nicht geprüft werden."
    private_key="$(openssl pkey -in "$key" -pubout 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')" || die "Privatschlüssel konnte nicht geprüft werden."
    [[ "$cert_key" == "$private_key" ]] || die "Zertifikat und Privatschlüssel gehören nicht zusammen."
}

create_ca() {
    require_apply
    require_absolute_dir "$ca_dir" "CA-Verzeichnis"
    [[ ! -e "$ca_dir" || -d "$ca_dir" ]] || die "CA-Ziel ist kein Verzeichnis."
    mkdir -p "$ca_dir"
    chmod 700 "$ca_dir"
    [[ ! -e "$ca_dir/ca.key" && ! -e "$ca_dir/ca.crt" ]] || die "CA-Dateien existieren bereits; kein Überschreiben."
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$ca_dir/ca.key" >/dev/null 2>&1
    chmod 600 "$ca_dir/ca.key"
    openssl req -x509 -new -sha256 -days "$days" \
        -key "$ca_dir/ca.key" -out "$ca_dir/ca.crt" \
        -subj "/CN=Smart Homelab Maintenance CA" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:1" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" >/dev/null 2>&1
    chmod 644 "$ca_dir/ca.crt"
    info "CA erstellt: öffentliches Zertifikat $ca_dir/ca.crt"
}

issue_certificate() {
    require_apply
    require_absolute_dir "$ca_dir" "CA-Verzeichnis"
    require_absolute_dir "$output_dir" "Ausgabeverzeichnis"
    [[ -n "$ip_address" ]] || die "--ip ist erforderlich."
    validate_ip "$ip_address" || die "IP muss eine private IPv4/IPv6-Adresse sein."
    [[ -r "$ca_dir/ca.key" && -r "$ca_dir/ca.crt" ]] || die "CA-Dateien fehlen."
    mkdir -p "$output_dir"
    chmod 700 "$output_dir"
    local key="$output_dir/$prefix.key" cert="$output_dir/$prefix.crt" csr ext serial
    [[ ! -e "$key" && ! -e "$cert" ]] || die "Zielzertifikat existiert bereits; kein Überschreiben."
    csr="$(mktemp)"; ext="$(mktemp)"; serial="$ca_dir/ca-cert.srl"
    trap 'rm -f -- "$csr" "$ext"' RETURN
    printf 'subjectAltName=critical,IP:%s\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n' "$ip_address" >"$ext"
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$key" >/dev/null 2>&1
    chmod 600 "$key"
    openssl req -new -sha256 -key "$key" -out "$csr" -subj "/CN=Smart Homelab Maintenance Agent"
    openssl x509 -req -sha256 -days "$days" -in "$csr" \
        -CA "$ca_dir/ca.crt" -CAkey "$ca_dir/ca.key" -CAserial "$serial" -CAcreateserial \
        -out "$cert" -extfile "$ext" >/dev/null 2>&1
    chmod 644 "$cert"
    verify_pair "$cert" "$key" "$ip_address" "$ca_dir/ca.crt"
    trap - RETURN
    rm -f -- "$csr" "$ext"
    info "Zertifikat erstellt: öffentliches Zertifikat $cert"
}

issue_self_signed_certificate() {
    require_apply
    require_absolute_dir "$output_dir" "Ausgabeverzeichnis"
    [[ -n "$ip_address" ]] || die "--ip ist erforderlich."
    validate_ip "$ip_address" || die "IP muss eine private IPv4/IPv6-Adresse sein."
    mkdir -p "$output_dir"
    chmod 700 "$output_dir"
    local key="$output_dir/$prefix.key" cert="$output_dir/$prefix.crt"
    [[ ! -e "$key" && ! -e "$cert" ]] || die "Zielzertifikat existiert bereits; kein Überschreiben."
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$key" >/dev/null 2>&1
    chmod 600 "$key"
    openssl req -x509 -new -sha256 -days "$days" \
        -key "$key" -out "$cert" \
        -subj "/CN=Smart Homelab Maintenance Agent" \
        -addext "subjectAltName=critical,IP:$ip_address" \
        -addext "basicConstraints=critical,CA:FALSE" \
        -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
        -addext "extendedKeyUsage=serverAuth" >/dev/null 2>&1
    chmod 644 "$cert"
    verify_self_signed "$cert" "$key" "$ip_address"
    info "Selbstsigniertes Zertifikat erstellt: öffentliches Zertifikat $cert"
}

verify_self_signed() {
    local cert="$1" key="$2" expected_ip="$3"
    [[ -r "$cert" && -f "$cert" ]] || die "Zertifikat fehlt oder ist nicht lesbar."
    [[ -r "$key" && -f "$key" ]] || die "Privatschlüssel fehlt oder ist nicht lesbar."
    openssl x509 -in "$cert" -noout -checkend 86400 >/dev/null || die "Zertifikat ist ungültig oder läuft in weniger als 24 Stunden ab."
    openssl x509 -in "$cert" -noout -checkip "$expected_ip" >/dev/null || die "Zertifikat enthält keinen passenden IP-SAN."
    openssl verify -CAfile "$cert" "$cert" >/dev/null || die "Selbstsigniertes Zertifikat konnte nicht als expliziter Trust Anchor geprüft werden."
    openssl x509 -in "$cert" -noout -text | grep -Fq "CA:FALSE" || die "Zertifikat ist keine End-Entity."
    openssl x509 -in "$cert" -noout -text | grep -Fq "TLS Web Server Authentication" || die "Zertifikat ist nicht für Server-Authentifizierung ausgestellt."
    local cert_key private_key issuer_subject
    cert_key="$(openssl x509 -in "$cert" -pubkey -noout | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')" || die "Zertifikat konnte nicht geprüft werden."
    private_key="$(openssl pkey -in "$key" -pubout 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')" || die "Zertifikat konnte nicht geprüft werden."
    [[ "$cert_key" == "$private_key" ]] || die "Zertifikat und Privatschlüssel gehören nicht zusammen."
    issuer_subject="$(openssl x509 -in "$cert" -noout -issuer -subject | sed 's/^issuer=//; s/^subject=//')"
    [[ "$(printf '%s\n' "$issuer_subject" | sed -n '1p')" == "$(printf '%s\n' "$issuer_subject" | sed -n '2p')" ]] || die "Zertifikat ist nicht selbstsigniert."
}

verify_certificate() {
    [[ -n "$ca_dir" && -n "$candidate_cert" && -n "$candidate_key" && -n "$ip_address" ]] || die "verify benötigt CA, Zertifikat, Schlüssel und --ip."
    validate_ip "$ip_address" || die "IP muss eine private IPv4/IPv6-Adresse sein."
    verify_pair "$candidate_cert" "$candidate_key" "$ip_address" "$ca_dir/ca.crt"
    info "Zertifikat, Kette, IP-SAN und Schlüssel-Paar sind gültig."
}

rotate_certificate() {
    require_apply
    require_absolute_dir "$target_dir" "Zielverzeichnis"
    validate_ip "$ip_address" || die "IP muss eine private IPv4/IPv6-Adresse sein."
    verify_pair "$candidate_cert" "$candidate_key" "$ip_address" "$ca_dir/ca.crt"
    mkdir -p "$target_dir"
    chmod 750 "$target_dir"
    local next_cert="$target_dir/.agent.crt.next" next_key="$target_dir/.agent.key.next"
    install -m 0644 "$candidate_cert" "$next_cert"
    install -m 0600 "$candidate_key" "$next_key"
    mv -f -- "$next_cert" "$target_dir/agent.crt"
    mv -f -- "$next_key" "$target_dir/agent.key"
    info "Zertifikat und Schlüssel atomar vorbereitet; kein Dienst wurde gestartet."
}

case "$ACTION" in
    init-ca) create_ca ;;
    issue|renew)
        [[ "$ACTION" != renew || "$prefix" != agent ]] || prefix="agent-renewed"
        issue_certificate
        ;;
    self-signed) issue_self_signed_certificate ;;
    verify) verify_certificate ;;
    rotate) rotate_certificate ;;
    *) usage >&2; die "Unbekannte Aktion: $ACTION" ;;
esac
