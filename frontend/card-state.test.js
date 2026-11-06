import assert from "node:assert/strict";
import { editorConfigChanged, modelFromHass, phaseLabel, preserveSelection, progressFor, updateLabel } from "./card-state.js";

const hass = { states: { "sensor.smart_homelab_maintenance_status": { state: "connected", attributes: { containers: [{ container_id: 101 }], jobs: [{ job_id: "j1", phase: "postcheck" }], available_updates: 1 } } } };
const model = modelFromHass(hass, {});
assert.equal(model.connected, true);
assert.equal(model.containers.length, 1);
assert.equal(phaseLabel(model.jobs[0]), "postcheck");
assert.equal(progressFor(model.jobs[0]), null);
assert.equal(preserveSelection({ selectedJob: "j1" }, model), "j1");
assert.equal(updateLabel({ update_supported: false }), "update_unknown");
assert.equal(updateLabel({ update_supported: true, installed_version: "1", available_version: "2" }), "update_available");
assert.equal(editorConfigChanged({ compact: false }, { compact: true }), true);
console.log("card-state tests passed");
