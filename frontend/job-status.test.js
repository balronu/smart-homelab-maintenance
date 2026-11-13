import assert from "node:assert/strict";
import { isActiveJob, isTerminalJob, jobActivityAt, jobResult, unwrapJobResponse } from "./job-status.js";

const accepted = { job_id: "0a36ae20-2397-460c-8445-3bc2120f0790", target: "container:101", state: "running", phase: "execution", created_at: "2026-11-13T10:00:00Z", message: "update started" };
assert.equal(isActiveJob(accepted), true);
assert.equal(isTerminalJob(accepted), false);
assert.equal(jobResult(accepted), null);
assert.equal(jobActivityAt(accepted), accepted.created_at);
assert.equal(isTerminalJob({ ...accepted, state: "succeeded", finished_at: "2026-11-13T10:02:00Z" }), true);
assert.equal(jobResult({ ...accepted, state: "succeeded" }), "Completed successfully");
assert.match(jobResult({ ...accepted, state: "blocked", message: "fresh update plan is unavailable" }), /fresh update plan/);
assert.match(jobResult({ ...accepted, state: "reconciled_legacy_state_verified" }), /Historical state verified/);
assert.deepEqual(unwrapJobResponse({ response: { data: { job_id: "j1", state: "queued" } } }), { job_id: "j1", state: "queued" });
console.log("job-status tests passed");
