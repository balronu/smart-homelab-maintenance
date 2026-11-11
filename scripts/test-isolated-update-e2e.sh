#!/usr/bin/env bash
set -Eeuo pipefail

# Phase 56 acceptance lane.  This is intentionally a disposable Debian
# rootfs, not a Proxmox LXC.  The fixed /usr/sbin/pct adapter below only
# translates the helper's numeric-ID contract to systemd-nspawn; it accepts
# no guest command from the test and is removed on every exit path.

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
AGENT_NAME="smart-homelab-maintenance"
SERVICE_USER="$AGENT_NAME"
ROOTFS="$(mktemp -d /var/lib/smh-phase56-rootfs.XXXXXX)"
WORK="$(mktemp -d /var/lib/smh-phase56-work.XXXXXX)"
chmod 0755 "$WORK"
PCT_ADAPTER="/usr/sbin/pct"
CREATED_GROUP=0
CREATED_USER=0

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
cleanup() {
  set +e
  systemctl stop "${AGENT_NAME}-lxc-helper.service" >/dev/null 2>&1 || true
  systemctl disable "${AGENT_NAME}-lxc-helper.service" >/dev/null 2>&1 || true
  systemctl disable "${AGENT_NAME}-agent.service" >/dev/null 2>&1 || true
  rm -f /etc/systemd/system/${AGENT_NAME}-lxc-helper.service
  rm -f /etc/systemd/system/${AGENT_NAME}-agent.service
  rm -rf /etc/systemd/system/${AGENT_NAME}-lxc-helper.service.d
  rm -f /usr/libexec/${AGENT_NAME}/lxc-apt-helper
  rm -f /etc/${AGENT_NAME}/lxc-apt-allowlist.toml
  rmdir /usr/libexec/${AGENT_NAME} /etc/${AGENT_NAME} 2>/dev/null || true
  rm -f "$PCT_ADAPTER"
  systemctl daemon-reload >/dev/null 2>&1 || true
  if [[ "$CREATED_USER" -eq 1 ]]; then userdel "$SERVICE_USER" >/dev/null 2>&1 || true; fi
  if [[ "$CREATED_GROUP" -eq 1 ]]; then groupdel "$SERVICE_USER" >/dev/null 2>&1 || true; fi
  rm -rf -- "$ROOTFS" "$WORK"
}
trap cleanup EXIT

[[ "$EUID" -eq 0 ]] || die "root is required"
[[ "$(readlink /proc/1/exe)" == */systemd ]] || die "PID 1 is not systemd"
command -v debootstrap >/dev/null || die "debootstrap is required"
command -v systemd-nspawn >/dev/null || die "systemd-nspawn is required"
command -v dpkg-scanpackages >/dev/null || die "dpkg-scanpackages is required"
for path in "$PCT_ADAPTER" "/etc/systemd/system/${AGENT_NAME}-lxc-helper.service" "/usr/libexec/${AGENT_NAME}/lxc-apt-helper" "/etc/${AGENT_NAME}/lxc-apt-allowlist.toml"; do
  [[ ! -e "$path" ]] || die "pre-existing target refuses test: $path"
done

getent group "$SERVICE_USER" >/dev/null 2>&1 || { groupadd --system "$SERVICE_USER"; CREATED_GROUP=1; }
getent passwd "$SERVICE_USER" >/dev/null 2>&1 || {
  useradd --system --no-create-home --shell /usr/sbin/nologin --gid "$SERVICE_USER" "$SERVICE_USER"
  CREATED_USER=1
}
chown "$SERVICE_USER:$SERVICE_USER" "$WORK"

cat > "/etc/systemd/system/${AGENT_NAME}-agent.service" <<'EOF'
[Unit]
Description=Ephemeral Phase 56 agent test anchor
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "${AGENT_NAME}-agent.service" >/dev/null

debootstrap --variant=minbase --include=apt,dpkg,systemd,systemd-sysv,ca-certificates \
  bookworm "$ROOTFS" https://deb.debian.org/debian >/dev/null

mkdir -p "$WORK/pkg/DEBIAN" "$WORK/pkg/usr/share/smh-e2e" "$ROOTFS/opt/smh-repo"
cat > "$WORK/pkg/DEBIAN/control" <<'EOF'
Package: smh-e2e-fixture
Version: 1.0
Architecture: all
Maintainer: Smart Homelab Maintenance
Description: disposable Phase 56 package acceptance fixture
EOF
printf '%s\n' fixture-v1 > "$WORK/pkg/usr/share/smh-e2e/version"
dpkg-deb --build "$WORK/pkg" "$WORK/smh-e2e-fixture_1.0_all.deb" >/dev/null
sed -i 's/^Version: 1.0$/Version: 2.0/' "$WORK/pkg/DEBIAN/control"
printf '%s\n' fixture-v2 > "$WORK/pkg/usr/share/smh-e2e/version"
dpkg-deb --build "$WORK/pkg" "$WORK/smh-e2e-fixture_2.0_all.deb" >/dev/null
cp "$WORK/smh-e2e-fixture_1.0_all.deb" "$ROOTFS/opt/smh-repo/"
cp "$WORK/smh-e2e-fixture_2.0_all.deb" "$ROOTFS/opt/smh-repo/"
(
  cd "$ROOTFS/opt/smh-repo"
  dpkg-scanpackages --multiversion . /dev/null > Packages
  gzip -9c Packages > Packages.gz
)
mkdir -p "$ROOTFS/etc/apt/sources.list.d"
printf '%s\n' 'deb [trusted=yes] file:/opt/smh-repo ./' > "$ROOTFS/etc/apt/sources.list.d/smh-e2e.list"
systemd-nspawn -D "$ROOTFS" --quiet dpkg -i /opt/smh-repo/smh-e2e-fixture_1.0_all.deb >/dev/null
systemd-nspawn -D "$ROOTFS" --quiet apt-get update >/dev/null
test "$(systemd-nspawn -D "$ROOTFS" --quiet dpkg-query -W -f='${Version}' smh-e2e-fixture)" = 1.0

# Fixed transport adapter: only status and the exact helper argv are accepted.
cat > "$PCT_ADAPTER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOTFS="__SMH_PHASE56_ROOTFS__"
[[ "$#" -ge 2 ]] || exit 2
case "$1" in
  status)
    [[ "$#" -eq 2 && "$2" == 321 ]] || exit 2
    printf '%s\n' 'status: running'
    ;;
  exec)
    [[ "$#" -ge 4 && "$2" == 321 && "$3" == -- ]] || exit 2
    shift 3
    case "${1:-}" in
      /usr/bin/cat)
        [[ "$#" -eq 2 && "$2" == /etc/os-release ]] || exit 2 ;;
      /usr/bin/test)
        [[ "$#" -eq 3 && "$2" == -x && ( "$3" == /usr/bin/apt || "$3" == /usr/bin/apt-get ) ]] || exit 2 ;;
      /usr/bin/apt|/usr/bin/apt-get)
        : ;;
      *) exit 2 ;;
    esac
    exec /usr/sbin/chroot "$ROOTFS" "$@"
    ;;
  *) exit 2 ;;
esac
EOF
sed -i "s#__SMH_PHASE56_ROOTFS__#$ROOTFS#" "$PCT_ADAPTER"
chmod 0755 "$PCT_ADAPTER"

export ROOT_DIR ROOTFS WORK
mkdir -p "/etc/systemd/system/${AGENT_NAME}-lxc-helper.service.d"
cat > "/etc/systemd/system/${AGENT_NAME}-lxc-helper.service.d/phase56-rootfs.conf" <<EOF
[Service]
ReadWritePaths=$ROOTFS
EOF
systemctl daemon-reload
"$ROOT_DIR/scripts/install-lxc-helper.sh" --source-dir "$ROOT_DIR" --expected-commit "$(git -C "$ROOT_DIR" rev-parse HEAD)" --apply --start

PYTHONPATH="$ROOT_DIR/agent" python3 - <<'PY'
import json, os, subprocess, time
import pwd
from pathlib import Path

from smart_homelab_maintenance.api import ApiApplication
from smart_homelab_maintenance.discovery import DiscoveryService, FixtureProxmoxBackend
from smart_homelab_maintenance.jobs import JobRepository
from smart_homelab_maintenance.permissions import PermissionStore, PolicyHelperTransport
from smart_homelab_maintenance.types import JobState
from smart_homelab_maintenance.updates import AptCommandRunner, AptUpdateReader, ProbeTarget, RootHelperTransport, UpdateService

token = "phase56-test-token"
transport = RootHelperTransport()
target = ProbeTarget("container:321", "phase56-debian", 321, "Debian", "12", "apt", False, True, False)
# Import as root so the checkout is readable, then use the exact agent UID for
# every socket/database operation. The helper's SO_PEERCRED gate is therefore
# exercised exactly as it is in deployment.
agent_user = pwd.getpwnam("smart-homelab-maintenance")
os.setgid(agent_user.pw_gid)
os.setuid(agent_user.pw_uid)
jobs = JobRepository(str(Path(os.environ["WORK"]) / "jobs.sqlite"))
service = UpdateService(
    lambda: [target], runner=AptCommandRunner(guest_transport=transport),
    reader=AptUpdateReader(guest_transport=transport), execution_enabled=True,
    permission_store=PermissionStore("/etc/smart-homelab-maintenance/lxc-apt-allowlist.toml", require_root=True, privileged_transport=PolicyHelperTransport()),
    jobs=jobs,
)
app = ApiApplication(DiscoveryService(FixtureProxmoxBackend([])), jobs, updates=service, read_token=token)

def call(method, path, body=None, auth=True):
    headers = {"Authorization": f"Bearer {token}"} if auth else {}
    raw = None if body is None else json.dumps(body).encode()
    status, response = app.handle(method, path, headers=headers, body=raw)
    return status, response["data"] if status == 200 else response

assert call("GET", "/api/v1/health", auth=False)[0] == 200
assert call("GET", "/api/v1/capabilities")[1]["execution_enabled"] is True
assert call("GET", "/api/v1/updates/container:321")[0] == 200
status, permission = call("POST", "/api/v1/updates/container:321/permissions", {"confirm": True, "simulation_authorized": True, "update_authorized": True})
assert status == 200, permission
status, checked = call("GET", "/api/v1/updates/container:321")
assert status == 200 and checked["status"] == "updates_available", checked
assert checked["update_supported"] is True and checked["packages"]
old_digest = checked["plan_digest"]
status, dry = call("POST", "/api/v1/updates/container:321/dry-run", {"confirm": True})
assert status == 200 and dry["success"] and dry["safe"] and dry["plan_digest"] == old_digest, dry
status, missing_confirmation = call("POST", "/api/v1/updates/container:321/execute", {"confirm": True, "install_confirmed": False, "plan_digest": old_digest})
assert status == 400 and "confirmation" in str(missing_confirmation).lower()
status, result = call("POST", "/api/v1/updates/container:321/execute", {"confirm": True, "install_confirmed": True, "plan_digest": old_digest})
assert status == 200 and result["success"] and result["accepted"] and result["status"] == "running", result
job_id = result["job_id"]
deadline = time.monotonic() + 30
while True:
    job = call("GET", "/api/v1/jobs/" + job_id)[1]
    if job["state"] in {JobState.SUCCEEDED.value, JobState.FAILED.value, JobState.MANUAL_RECOVERY.value}:
        break
    assert time.monotonic() < deadline, job
    time.sleep(0.1)
assert job["state"] == JobState.SUCCEEDED.value and job["preflight_verified"] == 1 and job["postcheck_verified"] == 1, job
package_version = subprocess.run(
    ["systemd-nspawn", "-D", os.environ["ROOTFS"], "--quiet", "dpkg-query", "-W", "-f=${Version}", "smh-e2e-fixture"],
    check=True, capture_output=True, text=True,
).stdout.strip()
assert package_version == "2.0", package_version
events = call("GET", f"/api/v1/jobs/{job_id}/events?after=0&limit=50")[1]
assert events["events"]
status, revoked = call("POST", "/api/v1/updates/container:321/permissions", {"confirm": True, "simulation_authorized": False, "update_authorized": False})
assert status == 200 and revoked["simulation_authorized"] is False and revoked["update_authorized"] is False, revoked
print(json.dumps({"agent_api": "PASS", "package": "smh-e2e-fixture", "job_id": job_id, "state": job["state"], "postcheck_verified": job["postcheck_verified"], "permission_revoked": True}, sort_keys=True))
PY

systemctl stop "${AGENT_NAME}-lxc-helper.service"
PYTHONPATH="$ROOT_DIR/agent" python3 - <<'PY'
import os, pwd
from smart_homelab_maintenance.updates import RootHelperTransport, GuestHelperUnavailableError
agent_user = pwd.getpwnam("smart-homelab-maintenance")
os.setgid(agent_user.pw_gid)
os.setuid(agent_user.pw_uid)
try:
    RootHelperTransport().read(321)
except (GuestHelperUnavailableError, OSError):
    print("PASS: helper outage is surfaced without retry")
else:
    raise SystemExit("helper outage was not surfaced")
PY

printf '%s\n' 'PASS: Phase 56 isolated agent/helper/API/dpkg acceptance completed in disposable Debian rootfs'
