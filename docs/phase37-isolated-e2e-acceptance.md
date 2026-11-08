# Phase 37 – isolierte End-to-End-Abnahme

## Test boundary

The Phase-37 harness uses temporary files, injected inventory records and a
mocked fixed probe transport. It does not require or access Proxmox, systemd,
Home Assistant, guests, VMs, CT112, or the productive agent. The official
installer is inspected and syntax-checked; it is not executed against a live
host.

## Verified flow

```text
inventory → policy → fixed probe → eligibility → allowlist plan
→ explicit apply → atomic file → audit → API/HA status
```

The isolated tests cover Debian 12/13, Ubuntu, unsupported OS, stopped guest,
VM-shaped record, invalid IDs, no-guest-access `discover_only`, explicit
`auto_eligible`, new/removed/stopped records, stale/failed probes, idempotent
apply, secure file mode, serialized apply, audit failure and rollback without
rights expansion.

The root discovery service serializes probe calls and enforces a fixed request
shape, peer UID, timeout and bounded request/output contracts. The apply
controller is preview-only unless explicitly confirmed; audit failure restores
the previous allowlist content.

## Live wiring boundary

The production path is intentionally not enabled by this phase. A separate
authorized rollout still needs a real root/systemd test environment, verified
installer execution, service health evidence, API/HA end-to-end evidence, and
a new explicit approval before any helper, discovery socket or allowlist is
activated on `pve-home`.
