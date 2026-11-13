export const ACTIVE_JOB_STATES = new Set(["queued", "preflight", "waiting_confirmation", "running", "verifying", "postcheck"]);
export const SUCCESSFUL_JOB_STATES = new Set(["succeeded", "completed", "reconciled_completed"]);
export const FAILED_JOB_STATES = new Set(["failed", "timeout", "cancelled", "blocked", "manual_recovery_required", "interrupted", "recovery_pending", "recovery_blocked", "reconciled_not_executed", "reconciled_legacy_state_verified"]);
export function unwrapJobResponse(response) { const payload = response?.response ?? response; return payload?.data && typeof payload.data === "object" ? payload.data : payload; }
export function isActiveJob(job) { return ACTIVE_JOB_STATES.has(String(job?.state || "")); }
export function isSuccessfulJob(job) { return SUCCESSFUL_JOB_STATES.has(String(job?.state || "")); }
export function isFailedJob(job) { return FAILED_JOB_STATES.has(String(job?.state || "")); }
export function isTerminalJob(job) { return isSuccessfulJob(job) || isFailedJob(job); }
export function jobActivityAt(job) { return job?.last_activity_at || job?.finished_at || job?.started_at || job?.created_at || null; }
export function jobResult(job, german = false) { if (isSuccessfulJob(job)) return german ? "Erfolgreich abgeschlossen" : "Completed successfully"; if (isFailedJob(job)) { if (job.state === "reconciled_legacy_state_verified") return german ? "Historischer Zustand verifiziert; Ausführung bleibt unklar" : "Historical state verified; execution remains unclear"; return job.error_message || job.message || (german ? "Job nicht erfolgreich abgeschlossen" : "Job did not complete successfully"); } return null; }
export function rememberedJobKey(target) { return `smart-homelab-maintenance:job:${target}`; }
