# Controlled update execution preflight

## Current policy

The shipped default remains `execution_enabled=false`. The agent reads this
from its private configuration; the Home Assistant integration exposes the
read-only value through `/api/v1/capabilities`. There is no Lovelace control
that can change it, and the v1.0.3 work does not change the productive value.

The allowlist and the per-container permission store remain separate gates:

- `policy_mode` controls discovery/allowlist planning.
- The root-owned allowlist controls which running Debian/Ubuntu APT LXCs can
  be probed through the helper.
- `simulation_authorized` permits a read-only simulation.
- `update_authorized` permits real updates for that CTID only and can never
  grant simulation access or override the global execution gate.
- `execution_enabled` is the final global gate.

Host updates, VMs, stopped containers, unsupported operating systems, generic
shell commands, package removal, automatic repair, automatic retry, and
automatic reboot remain excluded.

## Activation procedure (not performed)

Changing `execution_enabled` from `false` to `true` is a separate productive
policy change and requires all of the following in order:

1. Read the actual agent health, API contract, capabilities, policy mode,
   allowlist and job repository state through the authenticated API.
2. Confirm helper integrity, private HTTPS/TLS, host resource gates and the
   exact selected test CTID.
3. Confirm the selected container is running, reachable, Debian/Ubuntu APT,
   and has independent simulation and update grants.
4. Confirm no unresolved or manual-recovery job exists.
5. Prepare the configuration change as a reviewable, reversible diff.
6. Obtain a separate explicit confirmation for this exact global policy
   change; a card permission change is not sufficient.
7. Apply the policy change through the supported agent configuration/deployment
   path and read back `execution_enabled=true`, policy, allowlist and grants.
8. Run a dry-run/readback-only acceptance before any package mutation.

No restart, policy write, grant write, package installation, or agent
configuration change was performed during v1.0.3 development.

## Installation gate

The card enables “Install updates” only when all of these are true for the
same CTID: running and reachable target, both grants confirmed, global
execution enabled, fresh successful simulation, unchanged package plan and
matching digest, no held/conflicting/removing packages, no unresolved job,
and a connected backend. The dialog lists target, package names and old/new
versions, safety risks, possible restart need, and asks for a separate
confirmation. Historical snapshots remain display-only.

## First productive test recommendation

CT105 OpenClaw is excluded as a first test because of its high disk usage.
CT107 paperless-ngx may be considered only after the preflight above and a
separate explicit approval naming the exact package plan. The first real
installation remains outstanding.
