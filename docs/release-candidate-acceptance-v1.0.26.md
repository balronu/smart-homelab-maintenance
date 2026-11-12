# Release-candidate acceptance — update jobs and mobile dashboard

Status: **candidate prepared, not released**. This document records the
evidence for the continuation of PR #121 from Stable v1.0.26. No productive
Home Assistant or Proxmox system was changed.

## Implemented scope

- A timeout or unavailable helper during read-only preflight remains a
  `BLOCKED` job with an explicit preflight error and cannot be reported as a
  successful update.
- A read-only `repair-check` evaluates one job. Only a proven pre-mutation
  block is repairable; an unknown execution state is refused.
- Confirmed preflight repair records an append-only audit event and closes the
  job as `RECONCILED_NOT_EXECUTED`. It does not retry, run APT/dpkg, delete
  history, or alter package state.
- The card exposes **Jetzt auf Updates prüfen**, per-container forced checks,
  bounded live job summaries, **Fortschritt anzeigen**, **Details anzeigen**,
  **Reparatur prüfen**, and—only after a safe inspection and confirmation—
  **Reparatur durchführen**.
- The frontend bundle in `frontend/` and the installed custom-component copy
  are byte-identical.

## Acceptance matrix

| Scenario | Result | Evidence / limitation |
|---|---|---|
| Update check for all containers | PASS | Offline API/coordinator tests; forced refresh path |
| Update check for one container | PASS | Target validation and forced target path |
| No updates available | PASS | Existing update-service regression suite |
| Updates available | PASS | Existing update-service regression suite |
| Simulation succeeds | PASS | Existing isolated update tests |
| Simulation fails | PASS | Existing isolated update tests |
| Actual update completes successfully | NOT TESTED | No productive or non-isolated package mutation permitted |
| Actual update fails during mutation | NOT TESTED | Requires isolated mutation fixture not present in this checkout |
| Helper timeout before mutation | PASS | Preflight regression; update call is not reached |
| Package-installation failure | PASS | Existing worker/error-path tests; no live package mutation |
| Job survives HA reload | PASS | Persistent job repository and existing restart tests |
| Live status during a job | PASS | Bounded job projection and frontend state tests |
| Connection loss/reconnect | PASS | Existing transport/coordinator tests |
| Repair check for proven preflight failure | PASS | Read-only repository regression tests |
| Repair refused for unknown execution state | PASS | Read-only repository regression tests |
| Duplicate execution prevented | PASS | Existing idempotency/active-job tests |
| iPhone scroll in authenticated HA-iOS WebView | NOT TESTED | No authenticated iPhone node/WebView was available |
| iPad portrait/landscape layout | NOT TESTED | No authenticated iOS/iPad renderer was available |
| Desktop layout and card bundle | PASS | Node syntax, card-state tests, bundle comparison |
| Marketplace installation and upgrade from v1.0.26 | NOT TESTED | Requires a published candidate and user-side HA installation |

Local offline result for the complete non-socket suite: **239 passed, 12
subtests passed**. The intentionally socket-based HA runtime/lifecycle tests
are not included in that command because the shared test environment enables a
socket-blocking pytest plugin; they require the repository CI harness.

## CT101 boundary

The known CT101 job remains untouched. The existing evidence identifies the
failure as a read-only inspect timeout before package mutation. No unlock,
retry, APT/dpkg command, container restart, or recovery was performed by this
candidate work.

## Installation hand-off (after an approved release)

1. In Home Assistant, install the approved repository release through the
   configured Marketplace/HACS source; do not copy frontend files manually.
2. Upgrade the existing `smart_homelab_maintenance` integration from v1.0.26,
   preserving its existing Config Entry and options.
3. Restart Home Assistant when HA requests it so the integration registers the
   versioned card resource.
4. Confirm the card resource is loaded and reload the **Updates & Wartung**
   dashboard. Use **Jetzt auf Updates prüfen** for a non-installing refresh.

The final release must still verify the Marketplace metadata, release asset,
cache version, and HA runtime installation in CI or a dedicated isolated HA
fixture before it is called installable.

## Open release gates

- Authenticated iPhone/iPad validation remains open; desktop evidence is not a
  substitute for the requested HA-iOS WebView evidence.
- A true package-mutation E2E test must run in the designated isolated test
  environment.
- PR CI must pass on the final commit before any release preparation.
- No merge, tag, Stable release, or productive installation is part of this
  candidate hand-off.
