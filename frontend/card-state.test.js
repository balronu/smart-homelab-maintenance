import assert from "node:assert/strict";
import { editorConfigChanged, modelFromHass, phaseLabel, preserveSelection, progressFor, updateLabel } from "./card-state.js";

const hass = { states: {
  "sensor.smart_homelab_maintenance_agent_connection": { state: "connected", attributes: {}, last_updated: "2026-11-06T12:00:00+00:00" },
  "sensor.smart_homelab_maintenance_agent_compatibility": { state: "outdated", attributes: { agent_version: "0.1.0-beta.17" } },
  "sensor.smart_homelab_maintenance_host": { state: "pve-home", last_updated: "2026-11-06T12:01:00+00:00", attributes: { online: true, cpu_percent: 12.5, memory_used_bytes: 50, memory_total_bytes: 100 } },
  "sensor.smart_homelab_maintenance_vm_104": { state: "running", attributes: { vmid: 104, name: "haos" } },
  "sensor.smart_homelab_maintenance_container_101": { state: "stopped", attributes: { container_id: 101, name: "cloudflared" } },
  "sensor.smart_homelab_maintenance_running_jobs": { state: "0", attributes: {} },
  "sensor.smart_homelab_maintenance_status": { state: "connected", attributes: { jobs: [{ job_id: "j1", phase: "postcheck" }], available_updates: 1 } }
} };
const model = modelFromHass(hass, {});
assert.equal(model.connected, true);
assert.equal(model.containers.length, 1);
assert.equal(model.virtual_machines[0].vmid, 104);
assert.equal(model.host.name, "pve-home");
assert.equal(model.compatibility, "outdated");
assert.equal(model.last_updated, "2026-11-06T12:01:00+00:00");
assert.equal(phaseLabel(model.jobs[0]), "postcheck");
assert.equal(progressFor(model.jobs[0]), null);
assert.equal(preserveSelection({ selectedJob: "j1" }, model), "j1");
assert.equal(updateLabel({ update_supported: false }), "update_unknown");
assert.equal(updateLabel({ update_supported: true, installed_version: "1", available_version: "2" }), "update_available");
assert.equal(editorConfigChanged({ compact: false }, { compact: true }), true);
console.log("card-state tests passed");
