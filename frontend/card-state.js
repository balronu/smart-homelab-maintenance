// DOM-free state helpers for the Lovelace card and its tests.
export const DEFAULT_CONFIG = {
  title: "Smart Homelab Maintenance",
  data_entity: "sensor.smart_homelab_maintenance_status",
  compact: false,
  show_resources: true,
  show_jobs: true,
  max_containers: 20,
};

export function labels(locale = "de") {
  return locale.toLowerCase().startsWith("en") ? {
    connected: "Connected", offline: "Agent unreachable", containers: "Containers", updates: "Updates", blocked: "Blocked", jobs: "Jobs", jobsTitle: "Update jobs", noJobs: "No jobs", noApps: "No applications detected", running: "running", stopped: "stopped", unknownVersion: "Version unknown",
  } : {
    connected: "Verbunden", offline: "Agent nicht erreichbar", containers: "Container", updates: "Updates", blocked: "Blockiert", jobs: "Jobs", jobsTitle: "Updatejobs", noJobs: "Keine Jobs", noApps: "Keine Anwendungen erkannt", running: "running", stopped: "stopped", unknownVersion: "Version unbekannt",
  };
}

export function normalizeConfig(config = {}) {
  const result = { ...DEFAULT_CONFIG, ...config };
  result.max_containers = Math.max(1, Math.min(100, Number(result.max_containers) || 20));
  return result;
}

export function modelFromHass(hass = {}, config = {}) {
  const effective = normalizeConfig(config);
  const state = hass.states?.[effective.data_entity] || {};
  const attrs = state.attributes || {};
  return {
    connected: attrs.connected === true || state.state === "connected",
    agent_version: attrs.agent_version ?? "unknown",
    last_check: attrs.last_check ?? null,
    containers: Array.isArray(attrs.containers) ? attrs.containers.slice(0, effective.max_containers) : [],
    updates: Number(attrs.available_updates || 0),
    blocked: Number(attrs.blocked_updates || 0),
    jobs: effective.show_jobs && Array.isArray(attrs.jobs) ? attrs.jobs : [],
    error: attrs.error || null,
  };
}

export function phaseLabel(job) {
  return job?.phase || job?.state || "unknown";
}

export function progressFor(job) {
  // Never invent percentages: the API may provide a phase only.
  return Number.isFinite(job?.progress) ? Math.max(0, Math.min(100, job.progress)) : null;
}

export function updateLabel(app) {
  if (!app?.update_supported) return "update_unknown";
  if (app.blocked_reasons?.length) return "update_blocked";
  if (app.available_version && app.installed_version && app.available_version !== app.installed_version) return "update_available";
  return "current";
}

export function preserveSelection(previous, model) {
  const ids = new Set((model.jobs || []).map((job) => job.job_id));
  return previous?.selectedJob && ids.has(previous.selectedJob) ? previous.selectedJob : null;
}

export function editorConfigChanged(previous = {}, next = {}) {
  return JSON.stringify(normalizeConfig(previous)) !== JSON.stringify(normalizeConfig(next));
}
