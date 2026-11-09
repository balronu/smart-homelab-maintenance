# Phase 56 – isolated RC1 package acceptance

## Scope and evidence class

The `Isolated RC1 package acceptance` workflow runs on a short-lived
`ubuntu-24.04` GitHub-hosted runner. It installs `debootstrap`, `dpkg-dev`,
and `systemd-container` only on that ephemeral runner. The test creates a
Debian 12 root filesystem under `/var/lib`, starts the root-owned helper as a real
systemd service, and deletes the service, socket, rootfs, package database,
test user/group, and transport adapter in a shell `trap` on success or error.

The package transaction is real: `dpkg` installs version 1.0 and the fixed
agent/helper workflow upgrades the same disposable package to version 2.0 via
`apt-get --yes --no-remove upgrade`. The test asserts the persistent job ID,
job events, exit code, postcheck, and final package version. It also checks
eligibility, split simulation/update permission, separate installation
confirmation, API health/capabilities, and helper outage handling.

## Deliberate Proxmox boundary

GitHub-hosted Actions cannot provide a Proxmox node, `/usr/sbin/pct`, the
Proxmox IPC socket, or a real LXC namespace. The workflow therefore installs a
fixed, disposable `/usr/sbin/pct` adapter that accepts only container ID 321,
`status`, and the helper's fixed commands, then executes those commands via a
bounded `chroot` into the Debian rootfs. `systemd-nspawn` is used for rootfs
preparation, but its nested machine setup is incompatible with the helper
unit's production-like sandbox on the hosted runner. The adapter does **not**
accept free-form guest commands and it is removed during cleanup.

Consequently this is a real Debian/APT/dpkg/systemd/helper/API acceptance, but
not a claim of Proxmox `pct` or real-LXC compatibility. A non-production
Proxmox test guest remains necessary for the final live-LXC transport gate.
No credentials, Proxmox endpoint, pve-home resource, VM104, grant, policy, or
productive service is used by this workflow.

## Negative and recovery coverage

The existing unit/CI gates remain authoritative for stale plans, malformed or
stopped targets, timeout/identity failures, no automatic retry, and
`manual_recovery_required` transitions. This workflow adds a live helper
outage check after the successful transaction and deliberately performs no
automatic repair or retry. The workflow is PR/manual only; it is not attached
to release-tag publication and does not merge or publish a release.
