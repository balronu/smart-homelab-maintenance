#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
INSTALLER="$ROOT_DIR/scripts/install-lxc-helper.sh"
EXPECTED_COMMIT="$(git -C "$ROOT_DIR" rev-parse HEAD)"
AGENT_NAME="smart-homelab-maintenance"
SERVICE_USER="$AGENT_NAME"
HELPER_ROOT="/usr/libexec/$AGENT_NAME"
ETC_ROOT="/etc/$AGENT_NAME"
STATE_ROOT="/var/lib/$AGENT_NAME"
AGENT_UNIT="/etc/systemd/system/${AGENT_NAME}-agent.service"
HELPER_UNIT="/etc/systemd/system/${AGENT_NAME}-lxc-helper.service"
DISCOVERY_UNIT="/etc/systemd/system/${AGENT_NAME}-lxc-discovery.service"
ALLOWLIST="$ETC_ROOT/lxc-apt-allowlist.toml"
HELPER_PATH="$HELPER_ROOT/lxc-apt-helper"
DISCOVERY_PATH="$HELPER_ROOT/lxc-discovery.py"
CREATED_GROUP=0
CREATED_USER=0

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
cleanup() {
  set +e
  systemctl stop "${AGENT_NAME}-lxc-helper.service" "${AGENT_NAME}-lxc-discovery.service" >/dev/null 2>&1 || true
  systemctl disable "${AGENT_NAME}-lxc-helper.service" "${AGENT_NAME}-lxc-discovery.service" >/dev/null 2>&1 || true
  systemctl disable "${AGENT_NAME}-agent.service" >/dev/null 2>&1 || true
  rm -f "$HELPER_UNIT" "$DISCOVERY_UNIT" "$AGENT_UNIT" "$HELPER_PATH" "$DISCOVERY_PATH" "$ALLOWLIST"
  rmdir "$HELPER_ROOT" "$ETC_ROOT" "$STATE_ROOT" 2>/dev/null || true
  systemctl daemon-reload >/dev/null 2>&1 || true
  if [[ "$CREATED_USER" -eq 1 ]]; then userdel "$SERVICE_USER" >/dev/null 2>&1 || true; fi
  if [[ "$CREATED_GROUP" -eq 1 ]]; then groupdel "$SERVICE_USER" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

[[ "$EUID" -eq 0 ]] || die "root is required"
[[ "$(readlink /proc/1/exe)" == */systemd ]] || { printf '%s\n' 'SKIP: PID1 is not systemd; no real installer test claimed.'; exit 0; }
systemd_state="$(systemctl is-system-running 2>/dev/null || true)"
if [[ ! "$systemd_state" =~ ^(running|degraded)$ ]]; then
  message="NOT RUN: PID1 is systemd, but systemctl is-system-running returned '$systemd_state'; no installer result is claimed."
  printf '%s\n' "$message"
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then printf '## Installer systemd acceptance\n\n- **NOT RUN:** `%s`\n' "$message" >> "$GITHUB_STEP_SUMMARY"; fi
  exit 0
fi

for path in "$HELPER_UNIT" "$DISCOVERY_UNIT" "$AGENT_UNIT" "$HELPER_PATH" "$DISCOVERY_PATH" "$ALLOWLIST" "$STATE_ROOT"; do
  [[ ! -e "$path" ]] || die "pre-existing target refuses test: $path"
done

getent group "$SERVICE_USER" >/dev/null 2>&1 || { groupadd --system "$SERVICE_USER"; CREATED_GROUP=1; }
getent passwd "$SERVICE_USER" >/dev/null 2>&1 || {
  useradd --system --no-create-home --shell /usr/sbin/nologin --gid "$SERVICE_USER" "$SERVICE_USER"
  CREATED_USER=1
}

cat > "$AGENT_UNIT" <<EOF
[Unit]
Description=Ephemeral installer test anchor
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "$AGENT_UNIT"
systemctl daemon-reload
systemctl enable "$AGENT_NAME-agent.service" >/dev/null

python3 -m py_compile "$ROOT_DIR/scripts/smh-lxc-apt-helper.py" "$ROOT_DIR/scripts/smh-lxc-discovery.py"
bash -n "$INSTALLER"
"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT"
"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --apply
[[ "$(stat -c '%u:%a' "$HELPER_PATH")" == "0:755" ]]
[[ "$(stat -c '%u:%a' "$HELPER_UNIT")" == "0:644" ]]
[[ "$(stat -c '%u:%a' "$DISCOVERY_PATH")" == "0:755" ]]
[[ "$(stat -c '%u:%a' "$ALLOWLIST")" == "0:600" ]]
systemd-analyze verify "$HELPER_UNIT" "$DISCOVERY_UNIT"

"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --apply --start
for unit in "${AGENT_NAME}-lxc-helper.service" "${AGENT_NAME}-lxc-discovery.service"; do
  systemctl is-active --quiet "$unit" || {
    systemctl status --no-pager "$unit" >&2 || true
    journalctl --no-pager -u "$unit" -n 40 >&2 || true
    die "$unit did not become active"
  }
done
[[ -S "/run/$AGENT_NAME/lxc-apt-helper.sock" ]]
[[ -S "/run/$AGENT_NAME/lxc-discovery.sock" ]]

printf '%s\n' '[containers."321"]' 'authorized = true' > "$ALLOWLIST"
chmod 0600 "$ALLOWLIST"
before_allowlist="$(sha256sum "$ALLOWLIST")"
"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --apply
[[ "$(sha256sum "$ALLOWLIST")" == "$before_allowlist" ]]

if "$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "0000000000000000000000000000000000000000"; then
  die "invalid expected commit was accepted"
fi

printf '%s\n' 'PASS: ephemeral root/systemd installer preflight, apply, repeat, health, permissions, sockets, and fail-closed identity checks'
