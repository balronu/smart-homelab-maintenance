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
PCT_FIXTURE_PATH="/usr/sbin/pct"
DISCOVERY_DROPIN_DIR="/etc/systemd/system/${AGENT_NAME}-lxc-discovery.service.d"
PCT_FIXTURE_CREATED=0
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
  if [[ "$PCT_FIXTURE_CREATED" -eq 1 ]]; then rm -f "$PCT_FIXTURE_PATH"; fi
  rmdir "$DISCOVERY_DROPIN_DIR" 2>/dev/null || true
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
"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --discovery-only
if "$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --discovery-only --apply; then
  die "discovery-only apply without confirmation was accepted"
fi
# Discovery-only apply must not install or start the helper, and must migrate
# a detached legacy socket without touching the helper contract.
install -d -m 0750 -o root -g "$SERVICE_USER" "/run/$AGENT_NAME"
python3 - <<'PY'
import os
import socket

path = "/run/smart-homelab-maintenance/lxc-discovery.sock"
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stale:
    stale.bind(path)
os.chmod(path, 0o660)
PY
"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --discovery-only --apply --confirm --start-discovery
systemctl is-active --quiet "${AGENT_NAME}-lxc-discovery.service"
[[ ! -e "$HELPER_UNIT" ]] || die "discovery-only mode installed helper unit"
[[ ! -e "$HELPER_PATH" ]] || die "discovery-only mode installed helper file"
[[ -S "/run/$AGENT_NAME/lxc-discovery.sock" ]] || die "discovery socket missing after discovery-only start"
systemctl stop "${AGENT_NAME}-lxc-discovery.service"

"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --apply
[[ "$(stat -c '%u:%a' "$HELPER_PATH")" == "0:755" ]]
[[ "$(stat -c '%u:%a' "$HELPER_UNIT")" == "0:644" ]]
[[ "$(stat -c '%u:%a' "$DISCOVERY_PATH")" == "0:755" ]]
[[ "$(stat -c '%u:%a' "$ALLOWLIST")" == "0:600" ]]
systemd-analyze verify "$HELPER_UNIT" "$DISCOVERY_UNIT"

# The real discovery subprocess is exercised under systemd below.  The
# disposable pct adapter opens AF_INET before returning fixed Debian fixture
# output; it is not a production command or a guest and is removed by cleanup.
[[ ! -e "$PCT_FIXTURE_PATH" ]] || die "refusing to replace pre-existing pct: $PCT_FIXTURE_PATH"
cat > "$PCT_FIXTURE_PATH" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${1:-}" == exec && "${2:-}" =~ ^[0-9]+$ && "${3:-}" == -- ]] || exit 2
python3 -c 'import socket; s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.bind(("127.0.0.1", 0)); s.close()'
shift 3
case "${1:-}" in
  /usr/bin/test)
    [[ "${2:-}" == -r && "${3:-}" == /etc/os-release ]] || [[ "${2:-}" == -x && "${3:-}" =~ ^/usr/bin/(apt-get|dpkg-query)$ ]]
    ;;
  /usr/bin/cat)
    [[ "${2:-}" == /etc/os-release ]] && printf 'ID=debian\nVERSION_ID="13"\n'
    ;;
  /usr/bin/apt-get)
    [[ "${2:-}" == --version ]] && printf 'apt 3.0.4 (amd64)\n'
    ;;
  /usr/bin/dpkg-query)
    [[ "${2:-}" == --version ]] && printf 'Debian dpkg-query fixture\n'
    ;;
  *) exit 2 ;;
esac
EOF
chmod 0755 "$PCT_FIXTURE_PATH"
PCT_FIXTURE_CREATED=1
trap cleanup EXIT

# Repeating discovery-only apply leaves the installed helper contract byte-identical.
helper_hash_before="$(sha256sum "$HELPER_PATH" "$HELPER_UNIT")"
"$INSTALLER" --source-dir "$ROOT_DIR" --expected-commit "$EXPECTED_COMMIT" --discovery-only --apply --confirm
helper_hash_after="$(sha256sum "$HELPER_PATH" "$HELPER_UNIT")"
[[ "$helper_hash_before" == "$helper_hash_after" ]] || die "discovery-only mode changed helper files"

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

probe_discovery() {
  runuser -u "$SERVICE_USER" -- python3 - "$@" <<'PY'
import json
import socket
import sys

path = "/run/smart-homelab-maintenance/lxc-discovery.sock"
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
    channel.settimeout(5)
    channel.connect(path)
    channel.sendall(b'{"container_id":321,"operation":"probe"}\n')
    response = json.loads(channel.makefile().readline())
print(json.dumps(response, sort_keys=True))
if len(sys.argv) > 1 and sys.argv[1] == "expect-failure":
    raise SystemExit(0 if response.get("ok") is False else 1)
raise SystemExit(0 if response.get("ok") is True else 1)
PY
}

# This is the regression proof: the actual service process invokes the actual
# fixed /usr/sbin/pct path inside its systemd sandbox, where the fixture must
# create an AF_INET socket.
probe_discovery

# Negative control: with the old AF_UNIX-only restriction, the same real
# probe must fail closed. Restore the corrected unit before continuing.
systemctl stop "${AGENT_NAME}-lxc-discovery.service"
install -d -m 0755 -o root -g root "$DISCOVERY_DROPIN_DIR"
cat > "$DISCOVERY_DROPIN_DIR/10-negative-af-unix-only.conf" <<'EOF'
[Service]
RestrictAddressFamilies=AF_UNIX
EOF
systemctl daemon-reload
systemctl start "${AGENT_NAME}-lxc-discovery.service"
wait_for_socket_ready "/run/$AGENT_NAME/lxc-discovery.sock"
probe_discovery expect-failure
rm -f "$DISCOVERY_DROPIN_DIR/10-negative-af-unix-only.conf"
rmdir "$DISCOVERY_DROPIN_DIR"
systemctl daemon-reload
systemctl restart "${AGENT_NAME}-lxc-discovery.service"
wait_for_socket_ready "/run/$AGENT_NAME/lxc-discovery.sock"
probe_discovery

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
