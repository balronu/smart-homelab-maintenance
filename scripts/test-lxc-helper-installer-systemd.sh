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
  rm -f "${PREFLIGHT_JSON:-}"
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
PREFLIGHT_JSON="$(mktemp /tmp/smh-lxc-helper-preflight.XXXXXX.json)"
python3 "$ROOT_DIR/scripts/lxc-helper-preflight.py" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" >"$PREFLIGHT_JSON"
grep -q '"decision":"GO"' "$PREFLIGHT_JSON"
"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT"
"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --apply
[[ "$(stat -c '%u:%a' "$HELPER_PATH")" == "0:755" ]]
[[ "$(stat -c '%u:%a' "$HELPER_UNIT")" == "0:644" ]]
[[ "$(stat -c '%u:%a' "$DISCOVERY_PATH")" == "0:755" ]]
[[ "$(stat -c '%u:%a' "$ALLOWLIST")" == "0:600" ]]
systemd-analyze verify "$HELPER_UNIT" "$DISCOVERY_UNIT"

# RuntimeDirectoryPreserve keeps the directory between service lifecycles.
# Seed only a kernel-detached, legacy-owned discovery socket to verify that
# the installer/start path migrates it safely instead of treating it as live.
install -d -m 0750 -o root -g "$SERVICE_USER" "/run/$AGENT_NAME"
python3 - <<'PY'
import os
import socket

path = "/run/smart-homelab-maintenance/lxc-discovery.sock"
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stale:
    stale.bind(path)
os.chmod(path, 0o660)
PY

"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --apply --start
for unit in "${AGENT_NAME}-lxc-helper.service" "${AGENT_NAME}-lxc-discovery.service"; do
  systemctl is-active --quiet "$unit" || {
    systemctl status --no-pager "$unit" >&2 || true
    journalctl --no-pager -u "$unit" -n 40 >&2 || true
    die "$unit did not become active"
  }
done
assert_socket() {
  local socket_path="$1"
  [[ -S "$socket_path" ]] || die "socket missing after lifecycle operation: $socket_path"
  [[ "$(stat -c '%u:%g:%a' "$socket_path")" == "0:$(id -g "$SERVICE_USER"):660" ]] || die "socket ownership/mode drifted: $socket_path"
}

wait_for_socket_ready() {
  local socket_path="$1"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if [[ -S "$socket_path" ]] && [[ "$(stat -c '%u:%g:%a' "$socket_path")" == "0:$(id -g "$SERVICE_USER"):660" ]]; then
      return 0
    fi
    sleep 0.2
  done
  systemctl status --no-pager "${AGENT_NAME}-lxc-helper.service" "${AGENT_NAME}-lxc-discovery.service" >&2 || true
  journalctl --no-pager -u "${AGENT_NAME}-lxc-helper.service" -u "${AGENT_NAME}-lxc-discovery.service" -n 40 >&2 || true
  die "socket did not reach expected ownership/mode: $socket_path"
}

for socket_path in "/run/$AGENT_NAME/lxc-apt-helper.sock" "/run/$AGENT_NAME/lxc-discovery.sock"; do
  wait_for_socket_ready "$socket_path"
done

# The two services share the directory but must preserve it independently.
# Restart each service while the other remains running and require both paths
# to remain reachable after every transition.
assert_socket "/run/$AGENT_NAME/lxc-apt-helper.sock"
assert_socket "/run/$AGENT_NAME/lxc-discovery.sock"
systemctl restart "${AGENT_NAME}-lxc-helper.service"
for socket_path in "/run/$AGENT_NAME/lxc-apt-helper.sock" "/run/$AGENT_NAME/lxc-discovery.sock"; do
  wait_for_socket_ready "$socket_path"
  assert_socket "$socket_path"
done
systemctl restart "${AGENT_NAME}-lxc-discovery.service"
for socket_path in "/run/$AGENT_NAME/lxc-apt-helper.sock" "/run/$AGENT_NAME/lxc-discovery.sock"; do
  wait_for_socket_ready "$socket_path"
  assert_socket "$socket_path"
done
for unit in "${AGENT_NAME}-lxc-helper.service" "${AGENT_NAME}-lxc-discovery.service" "${AGENT_NAME}-lxc-helper.service" "${AGENT_NAME}-lxc-discovery.service"; do
  systemctl restart "$unit"
  for socket_path in "/run/$AGENT_NAME/lxc-apt-helper.sock" "/run/$AGENT_NAME/lxc-discovery.sock"; do
    wait_for_socket_ready "$socket_path"
    assert_socket "$socket_path"
  done
done

# A complete stop must remove both application-owned sockets even though the
# shared runtime directory is preserved. A subsequent clean start must recreate
# both paths without stale-socket failures.
systemctl stop "${AGENT_NAME}-lxc-discovery.service" "${AGENT_NAME}-lxc-helper.service"
for socket_path in "/run/$AGENT_NAME/lxc-apt-helper.sock" "/run/$AGENT_NAME/lxc-discovery.sock"; do
  [[ ! -e "$socket_path" ]] || die "stale socket survived complete stop: $socket_path"
done
systemctl start "${AGENT_NAME}-lxc-helper.service" "${AGENT_NAME}-lxc-discovery.service"
for socket_path in "/run/$AGENT_NAME/lxc-apt-helper.sock" "/run/$AGENT_NAME/lxc-discovery.sock"; do
  wait_for_socket_ready "$socket_path"
  assert_socket "$socket_path"
done

# Exercise policy_set through the real helper socket while ProtectSystem=strict
# is active. The client is the exact unprivileged agent user; no guest command
# or package operation is involved.
runuser -u "$SERVICE_USER" -- python3 - <<'PY'
import json
import socket

socket_path = "/run/smart-homelab-maintenance/lxc-apt-helper.sock"

def call(request):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
        channel.settimeout(5)
        channel.connect(socket_path)
        channel.sendall((json.dumps(request, separators=(",", ":")) + "\n").encode())
        response = json.loads(channel.makefile().readline())
    if response.get("ok") is not True:
        raise SystemExit(response)
    return response

metadata = {"os_name": "Debian", "os_version": "13", "package_manager": "apt"}
call({"operation": "policy_set", "target": "container:321", "simulation_authorized": True, "update_authorized": False, "metadata": metadata, "confirm": True})
read = call({"operation": "policy_read"})
assert read["entries"]["321"]["simulation_authorized"] is True
call({"operation": "policy_set", "target": "container:321", "simulation_authorized": False, "update_authorized": False, "metadata": metadata, "confirm": True})
read = call({"operation": "policy_read"})
assert read["entries"]["321"]["simulation_authorized"] is False
PY
before_allowlist="$(sha256sum "$ALLOWLIST")"
"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --apply
[[ -f "$ALLOWLIST" && "$(stat -c '%u:%a' "$ALLOWLIST")" == "0:600" ]]
grep -q '\[containers\."321"\]' "$ALLOWLIST"
grep -q 'simulation_authorized = false' "$ALLOWLIST"

if "$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "0000000000000000000000000000000000000000"; then
  die "invalid expected commit was accepted"
fi

printf '%s\n' 'PASS: ephemeral root/systemd installer preflight, apply, repeat, health, permissions, sockets, and fail-closed identity checks'
