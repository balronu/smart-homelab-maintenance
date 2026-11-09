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
| Cancellation | Implemented fail-closed | Pre-mutation cancellation persists; running helper jobs refuse cancellation because no verifiable PID/PGID is exposed |
| iPhone/iPad/Desktop UI | Partially implemented and browser-tested | Responsive layout and simulation exist; iPhone/iPad native acceptance is not run |
| Two-step install confirmation | Candidate implemented | UI and API now require separate installation confirmation |
| Socket/service security | Implemented and CI-tested | Fixed Unix socket, peer checks, bounded requests/output, private allowlist |
| Reboot handling | Implemented as non-action | No automatic reboot; reboot-required state is not a productive acceptance result |
| Recovery after failure | Implemented with manual boundary | Restart/timeout/disconnect/postcheck uncertainty becomes persistent `manual_recovery_required`; no retry, rollback, `apt --fix-broken`, or `dpkg --configure -a` |

## Candidate changes

The isolated candidate branch adds:

* separate `install_confirmed` API/service confirmation;
* a final fixed APT simulation immediately before the mutating helper call;
* persisted update jobs with preflight, running, postcheck, success, failed,
  blocked, and manual-recovery outcomes;
* no automatic retry after timeout or uncertain transport state;
* persistent cancellation requests and target locks for active/manual-recovery jobs;
* process identity verification that refuses signals if PID start time or process
  group changes; the current helper exposes no identity, so running cancellation
  is intentionally refused;
* regression coverage for the second confirmation, final revalidation, and
  persisted job completion;
* German/English UI confirmation text.

The candidate deliberately does **not** enable execution, grant any target,
run an update, restart a guest, or change host policy.

## Phase-55 disposition of the seven pre-existing local failures

All seven failures were reproduced on the Phase-54 base and are now green in
the candidate suite. None was caused by the runner or by a missing external
service; each was a product contract or regression expectation that needed to
be made explicit.

1. **Allowlist removal omitted a present stopped target.** Cause: the plan
   retained an existing authorization for an inventory target that was no
   longer eligible. Product/security defect; Stable-relevant because stale
   authorization could survive reconciliation. Fixed by removing present but
   ineligible IDs and by updating the regression assertion.
2. **Unsupported OS was classified as unknown.** Cause: evidence completeness
   was checked before the OS allowlist. Product classification defect; Stable-
   relevant because unsupported guests must never look merely undiscovered.
   Fixed by classifying non-Debian/Ubuntu evidence as `unsupported` first.
3. **Malformed probe evidence was classified as unknown.** Cause: missing
   required APT evidence bypassed the malformed-output path. Product safety
   defect; Stable-relevant because malformed helper output must fail closed.
   Fixed with strict bounded type/size validation and `probe_failed`.
4. **Legacy/split grant status over-reported an ID.** Cause: status mapping
   treated a legacy-shaped entry as authorized without the required grant
   semantics. Product status/security defect; Stable-relevant because the UI
   must not imply update authority. Fixed with explicit legacy mapping and a
   regression assertion that excludes the unauthorized ID.
5. **Unsafe policy file mode was accepted.** Cause: the loader rejected only
   group/other write bits instead of requiring exact `0600`. Product security
   defect; Stable-critical because policy integrity is an authorization
   boundary. Fixed by requiring root ownership (when enabled) and exact mode
   `0600`.
6. **Reconcile leaked a transport exception.** Cause: probe exceptions were
   not converted to a safe probe result. Product resilience defect;
   Stable-relevant because a timeout/disconnect must not abort reconciliation
   or authorize anything. Fixed by converting unexpected probe failures to
   `probe_failed` and preserving fail-closed eligibility.
7. **Manual authorization leaked through failed probe handling.** Cause:
   failed/unavailable evidence was not normalized before allowlist planning.
   Product authorization defect; Stable-critical because a manual ID must not
   be auto-added from stale or failed evidence. Fixed by normalizing failed
   probes to unknown target metadata and testing the resulting removal.

The full regression run is `180 passed, 8 subtests passed`.

## Stable gates

| Gate | Result |
|---|---|
| Beta.49 exact main/tag/release state | PASS, verified read-only |
| Beta.49 main CI | PASS on exact merge SHA |
| Beta.49 tag CI | PASS after browser recovery, exact tag unchanged |
| HACS / Hassfest / HA runtime / Browser / Installer / Security | PASS for Beta.49 |
| Candidate local full suite | PASS: 180 tests and 8 subtests |
| Candidate PR CI | MUST PASS after Phase 55 push; PR remains open |
| Productive HA runtime | NOT RUN; separate approval required |
| Productive helper/allowlist activation | NOT RUN; separate approval required |
| Productive package update | NOT RUN and prohibited in this phase |
| Rollback of a real package transaction | BLOCKED by design; package rollback is not automatic and needs isolated administrative recovery |

## Required productive acceptance plan

1. Review and separately approve the candidate PR only after all required CI gates pass.
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

The complete scenario matrix is maintained in
`docs/isolated-update-acceptance.md`.
