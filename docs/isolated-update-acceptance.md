# Isolated update acceptance plan

This plan is prepared for a disposable Debian 12/13 or supported Ubuntu LXC.
It is not authorization to create a guest or execute packages. VM104,
pve-home, production LXCs, host packages, reboots, grants, credentials, and
snapshots are out of scope.

## Evidence rules

- Record exact agent/integration commit, guest image digest, target CTID, and
  `execution_enabled` before the test.
- Use only the fixed helper API; no guest shell text or free-form argv.
- Capture API response, persistent job row, event log, helper exit code, and
  postcheck. A timeout or disconnect is never considered success.
- Any uncertain package state ends with `manual_recovery_required`; do not run
  `apt --fix-broken`, `dpkg --configure -a`, retry, or reboot automatically.

## Scenarios and pass criteria

1. **Eligibility/discovery:** running Debian/Ubuntu APT passes; stopped,
   unsupported, malformed, missing, and legacy-grant targets are excluded.
2. **Simulation/details:** package names, old/new versions, held/conflict/
   removal data, digest, and timestamps are returned.
3. **Stale plan:** changed package list or digest blocks mutation before helper
   execution.
4. **Authorization:** revoked grants, malformed grants, and the global
   execution lock block mutation; revocation remains possible.
5. **Helper failures:** discovery/simulation/helper timeout or disconnect is
   visible and leaves no successful job.
6. **Cancellation:** queued/preflight jobs persist as cancelled; running jobs
   have no unsafe kill button and remain locked if identity is unavailable.
7. **Incomplete installation:** non-zero exit, postcheck failure, lost
   transport, or restart produces an auditable recovery state and blocks a new
   update for that target.
8. **One controlled mutation:** only after separate confirmations, run exactly
   one approved transaction; verify exit code, postcheck, no removal, no reboot,
   and no automatic retry.

The productive acceptance decision remains separate from this prepared plan.
