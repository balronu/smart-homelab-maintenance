# Stable-Readiness Audit – 2026-11-09

## Scope and decision

This audit starts from the published Beta.49 merge commit
`c461e5f4096a25c3e39eda2384f5d89474df0d20`. The audit branch is isolated and
does not change Home Assistant, VM104, pve-home, the agent, grants,
credentials, services, guests, backups, or snapshots. `execution_enabled`
remains `false`.

**Decision: NO-GO for Stable and productive package actions.** A separate
candidate branch adds the missing execution-safety contracts, but it is not
merged, installed, or released by this audit.

## Function matrix

| Function | Status | Evidence / limitation |
|---|---|---|
| HA/Agent API 1.1 compatibility | Implemented and CI-tested | Beta.49 manifest and runtime contract; productive HA remains not tested |
| Dynamic host/VM/LXC inventory | Implemented and CI-tested | Dynamic discovery tests; VM package actions are excluded |
| Automatic eligibility | Implemented and isolated-tested | Fixed probe proves running Debian/Ubuntu + APT; no productive helper activation |
| Policy preview/apply | Implemented and isolated-tested | Explicit generation/token/confirmation and atomic helper-mediated apply |
| Simulation permissions | Implemented and isolated-tested | Per-container grant, revocable, fail-closed helper policy |
| Update permissions | Implemented and isolated-tested | Separate grant; requires simulation grant; productive grants unchanged |
| APT simulation and package details | Implemented and CI-tested | Fixed commands and package parsing; no live guest simulation performed |
| Real update execution | Candidate implementation only | Beta.49 production config remains disabled; no productive package action |
| Immediate pre-execution revalidation | Candidate implemented | Candidate reruns fixed simulation and rejects changed/unsafe plans |
| Job status/progress/recovery | Candidate implemented | Candidate persists update jobs and marks uncertain transport/timeout as manual recovery |
| Cancellation | Incomplete | No safe cancellation contract exists for an already-running APT process |
| iPhone/iPad/Desktop UI | Partially implemented and browser-tested | Responsive layout and simulation exist; iPhone/iPad native acceptance is not run |
| Two-step install confirmation | Candidate implemented | UI and API now require separate installation confirmation |
| Socket/service security | Implemented and CI-tested | Fixed Unix socket, peer checks, bounded requests/output, private allowlist |
| Reboot handling | Implemented as non-action | No automatic reboot; reboot-required state is not a productive acceptance result |
| Recovery after failure | Partially implemented | Fail-closed job recovery exists; package-level rollback is not possible and must be documented |

## Candidate changes

The isolated candidate branch adds:

* separate `install_confirmed` API/service confirmation;
* a final fixed APT simulation immediately before the mutating helper call;
* persisted update jobs with preflight, running, postcheck, success, failed,
  blocked, and manual-recovery outcomes;
* no automatic retry after timeout or uncertain transport state;
* regression coverage for the second confirmation, final revalidation, and
  persisted job completion;
* German/English UI confirmation text.

The candidate deliberately does **not** enable execution, grant any target,
run an update, restart a guest, or change host policy.

## Stable gates

| Gate | Result |
|---|---|
| Beta.49 exact main/tag/release state | PASS, verified read-only |
| Beta.49 main CI | PASS on exact merge SHA |
| Beta.49 tag CI | PASS after browser recovery, exact tag unchanged |
| HACS / Hassfest / HA runtime / Browser / Installer / Security | PASS for Beta.49 |
| Candidate local focused tests | MUST PASS before PR is ready |
| Candidate PR CI | NOT RUN until branch is pushed |
| Productive HA runtime | NOT RUN; separate approval required |
| Productive helper/allowlist activation | NOT RUN; separate approval required |
| Productive package update | NOT RUN and prohibited in this phase |
| Rollback of a real package transaction | BLOCKED until an isolated package fixture proves the documented recovery boundary |

## Required productive acceptance plan

1. Approve and merge the candidate PR only after all required CI gates pass.
2. Install the exact agent/integration candidate in a disposable Debian/Ubuntu
   LXC fixture, never VM104 or pve-home.
3. Verify discovery, eligibility, simulation, package list, stale-plan
   rejection, permission revocation, helper/socket failure, timeout, and
   manual-recovery read-back.
4. Execute exactly one explicitly approved update in that disposable fixture;
   capture job events, both fixed APT phases, exit codes, postcheck, and any
   reboot-required indication. Do not auto-reboot.
5. Test incomplete/failed installation recovery and prove that no automatic
   retry occurs.
6. Separately approve production rollout and only then consider a Stable
   release. Stable publication itself needs a further explicit release
   approval.
