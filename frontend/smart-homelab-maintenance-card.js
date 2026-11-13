const DEFAULTS = { title: "Smart Homelab Maintenance", compact: false, show_maintenance: true, show_vms: true, show_containers: true };
export function resolveLanguage(hass) {
  const localeObjectLanguage = hass?.locale && typeof hass.locale === "object" && typeof hass.locale.language === "string"
    ? hass.locale.language
    : null;
  const candidates = [hass?.language, localeObjectLanguage, hass?.locale, hass?.config?.language];
  const raw = candidates.find((value) => typeof value === "string" && value.trim()) || "en";
  return raw.toLowerCase().startsWith("de") ? "de" : "en";
}
const textFor = (language) => language === "de" ? { connected: "Verbunden", offline: "Agent nicht erreichbar", hostOffline: "Host offline", overview: "Übersicht", host: "Proxmox-Host", lastUpdated: "Letzte Aktualisierung", vms: "Virtuelle Maschinen", containers: "LXC-Container", maintenance: "Wartung", running: "laufend", stopped: "gestoppt", unknown: "unbekannt", cpu: "CPU", memory: "RAM", storage: "Speicher", availableMemory: "Freier RAM", freeStorage: "Freier Speicher", version: "Version", kernel: "Kernel", uptime: "Laufzeit", jobs: "Laufende Jobs", noData: "Keine Daten verfügbar", noVms: "Keine VMs erkannt", noContainers: "Keine Container erkannt", error: "Fehler", readOnly: "Nur-Lese-Modus", updates: "Updates", simulate: "Update simulieren", install: "Updates installieren", installConfirm: "Die Simulation ist bestanden. Soll dieses konkrete Paket-Update jetzt wirklich installiert werden?", installDisabled: "Updatefunktion noch nicht freigegeben", simulateDisabled: "Simulation nicht verfügbar", unauthorizedReason: "Simulation nicht verfügbar: Ziel nicht autorisiert", helperUnavailableReason: "Simulation nicht verfügbar: Helper nicht eingerichtet", stoppedReason: "Simulation nicht verfügbar: Container ist gestoppt", unsupportedReason: "Simulation nicht verfügbar: Ziel nicht unterstützt", staleReason: "Simulation nicht verfügbar: Prüfdaten veraltet", notCheckedReason: "Simulation nicht verfügbar: Ziel noch nicht geprüft", vmExclusion: "Updates dieser virtuellen Maschine werden nicht über Smart Homelab Maintenance durchgeführt. Bitte die Updatefunktion des jeweiligen Gastbetriebssystems verwenden.", noUpdatesReason: "Keine verfügbaren Updates für die Simulation", current: "Aktuell", updatesAvailable: "verfügbar", notChecked: "Noch nicht geprüft", unsupported: "Nicht unterstützt", unauthorized: "Nicht autorisiert", failed: "Prüfung fehlgeschlagen", stale: "Daten veraltet", unknownUpdate: "Unbekannt", security: "Sicherheitsupdates", checked: "Letzte Prüfung", simulation: "Simulation", compatibility: "Agent-Kompatibilität", compatibilityCurrent: "Aktuell", compatibilityOutdated: "Veraltet", compatibilityIncompatible: "Inkompatibel", compatibilityUnknown: "Unbekannt" } : { connected: "Connected", offline: "Agent unreachable", hostOffline: "Host offline", overview: "Overview", host: "Proxmox host", lastUpdated: "Last updated", vms: "Virtual machines", containers: "LXC containers", maintenance: "Maintenance", running: "running", stopped: "stopped", unknown: "unknown", cpu: "CPU", memory: "RAM", storage: "Storage", availableMemory: "Free RAM", freeStorage: "Free storage", version: "Version", kernel: "Kernel", uptime: "Uptime", jobs: "Running jobs", noData: "No data available", noVms: "No virtual machines detected", noContainers: "No containers detected", error: "Error", readOnly: "Read-only mode", updates: "Updates", simulate: "Simulate update", install: "Install updates", installConfirm: "The simulation passed. Do you really want to install this specific package update now?", installDisabled: "Update function not released", simulateDisabled: "Simulation unavailable", unauthorizedReason: "Simulation unavailable: target is not authorized", helperUnavailableReason: "Simulation unavailable: helper is not configured", stoppedReason: "Simulation unavailable: container is stopped", unsupportedReason: "Simulation unavailable: target is not supported", staleReason: "Simulation unavailable: check data is stale", notCheckedReason: "Simulation unavailable: target has not been checked", vmExclusion: "Updates for this virtual machine are not performed through Smart Homelab Maintenance. Please use the update function of the respective guest operating system.", noUpdatesReason: "No updates are available for simulation", current: "Up to date", updatesAvailable: "available", notChecked: "Not checked", unsupported: "Not supported", unauthorized: "Not authorized", failed: "Check failed", stale: "Data is stale", unknownUpdate: "Unknown", security: "security updates", checked: "Last checked", simulation: "Simulation", compatibility: "Agent compatibility", compatibilityCurrent: "Current", compatibilityOutdated: "Outdated", compatibilityIncompatible: "Incompatible", compatibilityUnknown: "Unknown" };
const editorText = (language) => language === "de" ? { title: "Titel", vms: "Virtuelle Maschinen", containers: "LXC-Container", maintenance: "Wartung" } : { title: "Title", vms: "Virtual machines", containers: "LXC containers", maintenance: "Maintenance" };
const labelsFor = (language) => ({ ...textFor(language), refresh: language === "de" ? "Jetzt auf Updates prüfen" : "Check for updates now", repairCheck: language === "de" ? "Reparatur prüfen" : "Check repair need", repair: language === "de" ? "Reparatur durchführen" : "Perform repair", repairDetails: language === "de" ? "Details anzeigen" : "Show details", closeDetails: language === "de" ? "Details schließen" : "Hide details", runningJob: language === "de" ? "Fortschritt anzeigen" : "Show progress" });
const permissionText = (language) => language === "de" ? { allowSimulation: "Simulation freigeben", revokeSimulation: "Simulation widerrufen", allowUpdates: "Updates freigeben", revokeUpdates: "Updates widerrufen", permissionConfirm: "Berechtigung wirklich ändern?", permissionRunning: "Berechtigung wird geändert …", permissionPending: "Berechtigung geändert; HA-Rückread wird bestätigt …", permissionSuccess: "Berechtigung erfolgreich geändert.", permissionFailed: "Berechtigungsänderung fehlgeschlagen", permissionReadbackFailed: "Berechtigung geändert, aber der bestätigte Rückread fehlt." } : { allowSimulation: "Allow simulation", revokeSimulation: "Revoke simulation", allowUpdates: "Allow updates", revokeUpdates: "Revoke updates", permissionConfirm: "Really change this permission?", permissionRunning: "Changing permission …", permissionPending: "Permission changed; confirming HA readback …", permissionSuccess: "Permission changed successfully.", permissionFailed: "Permission change failed", permissionReadbackFailed: "Permission changed, but the confirmed readback is missing." };
const esc = (value) => String(value ?? "").replace(/[&<>\"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c]));
const bytes = (value) => { if (!Number.isFinite(Number(value))) return null; const units = ["B", "KB", "MB", "GB", "TB"]; let n = Number(value); let i = 0; while (Math.abs(n) >= 1024 && i < units.length - 1) { n /= 1024; i += 1; } return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`; };
const finiteMetric = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
const pct = (used, total) => finiteMetric(used) && finiteMetric(total) && Number(total) > 0 ? Math.max(0, Math.min(100, Number(used) / Number(total) * 100)) : null;
const uptime = (value) => Number.isFinite(Number(value)) ? `${Math.floor(Number(value) / 86400)}d ${Math.floor(Number(value) % 86400 / 3600)}h` : null;
function model(hass, config) {
  const states = hass?.states || {}; const connection = states["sensor.smart_homelab_maintenance_agent_connection"]; const reachable = states["binary_sensor.smart_homelab_maintenance_agent_reachable"]; const hostState = states["sensor.smart_homelab_maintenance_host"];
  const entities = Object.entries(states).filter(([id, state]) => id.startsWith("sensor.smart_homelab_maintenance_") && state?.attributes);
  const jobs = Array.isArray(states["sensor.smart_homelab_maintenance_running_jobs"]?.attributes?.jobs) ? states["sensor.smart_homelab_maintenance_running_jobs"].attributes.jobs : [];
  const jobsByTarget = new Map(jobs.map((job) => [job.target, job]));
  const project = ([entity_id, state]) => { const value = { entity_id, ...state.attributes, name: state.attributes?.name || state.attributes?.friendly_name || entity_id, running: typeof state.attributes?.running === "boolean" ? state.attributes.running : state.state === "running" }; const target = value.container_id != null ? `container:${value.container_id}` : value.vmid != null ? `vm:${value.vmid}` : null; return { ...value, job: target ? jobsByTarget.get(target) || null : null }; };
  const vms = entities.filter(([, state]) => state.attributes.vmid != null).map(project);
  const containers = entities.filter(([, state]) => state.attributes.container_id != null).map(project);
  const compatibilityState = states["sensor.smart_homelab_maintenance_agent_compatibility"];
  const errorState = connection?.attributes?.error || states["sensor.smart_homelab_maintenance_last_error"]?.state;
  const error = errorState && errorState !== "none" ? errorState : null;
  const connected = connection?.state === "connected" && reachable?.state === "on";
  const agentStatus = error ? "error" : connected ? "connected" : connection?.state === "offline" || reachable?.state === "off" ? "offline" : "unknown";
  const jobSensor = states["sensor.smart_homelab_maintenance_running_jobs"];
  return { connected, agentStatus, error, compatibility: compatibilityState?.state || "unknown", host: hostState ? { name: hostState.state, ...hostState.attributes } : null, lastUpdated: hostState?.last_updated || connection?.last_updated || null, vms, containers, jobs: jobSensor?.state ?? null, jobSummary: jobSensor?.attributes || {}, config };
}
const metric = (label, value, sub = "") => `<div class="metric"><span class="muted">${esc(label)}</span><strong>${esc(value ?? "–")}</strong>${sub ? `<span class="muted">${esc(sub)}</span>` : ""}</div>`;
function bar(label, used, total) { const value = pct(used, total); return value === null ? "" : `<div class="bar-row"><span>${esc(label)}</span><progress max="100" value="${value.toFixed(1)}"></progress><span class="muted">${value.toFixed(0)}%</span></div>`; }
function displayValue(value) { return value == null || value === "" || value === "unknown" || value === "unavailable" ? null : value; }
function recoveryText(summary, german) { const states = summary?.lifecycle_states || {}; const legacy = Number(states.reconciled_legacy_state_verified || 0); const blocked = Number(states.recovery_blocked || 0) + Number(states.manual_recovery_required || 0); const pending = Number(states.recovery_pending || 0) + Number(states.interrupted || 0); if (blocked) return german ? `Manuelle Prüfung erforderlich (${blocked}); ${summary.recovery_reasons?.[0] || "Recovery blockiert"}` : `Manual review required (${blocked}); ${summary.recovery_reasons?.[0] || "recovery blocked"}`; if (pending) return german ? `Jobstatus wird geprüft (${pending})` : `Job status is being checked (${pending})`; if (legacy) return german ? `Legacy-Zustand verifiziert (${legacy}); Historie bleibt unklar` : `Legacy state verified (${legacy}); history remains unclear`; if (Number(states.reconciled_not_executed || 0)) return german ? "Keine Paketänderung nachgewiesen" : "No package change verified"; if (Number(states.reconciled_completed || 0)) return german ? "Job erfolgreich reconciliert" : "Job successfully reconciled"; return ""; }
function localizedUpdateError(update, labels) { const raw = String(update?.error || "").toLowerCase(); if (update?.simulation_reason === "helper-unavailable" || raw.includes("helper is unavailable")) return labels.helperUnavailableReason; if (update?.simulation_reason === "target-not-running-or-not-checked") return labels.stoppedReason; if (update?.status === "unauthorized" || raw.includes("not authorized") || raw.includes("unauthorized")) return labels.unauthorizedReason; if (raw.includes("authorized guest package access is unavailable")) return labels.unauthorizedReason.startsWith("Simulation") ? "Gastzugriff für Pakete ist nicht verfügbar." : "Authorized guest package access is unavailable."; if (update?.status === "unsupported" || raw.includes("not supported") || raw.includes("unsupported")) return labels.unsupportedReason; if (update?.status === "stale" || raw.includes("stale")) return labels.staleReason; return update?.error || ""; }
function updateText(update, labels) { if (!update || !update.status) return ""; const count = Number.isFinite(Number(update.available_count)) ? `: ${update.available_count} ${labels.updatesAvailable}` : ""; const security = Number(update.security_count) > 0 ? ` · ${update.security_count} ${labels.security}` : ""; const status = { updates_available: `${labels.updates}${count}${security}`, current: `${labels.updates}: ${labels.current}`, not_checked: `${labels.updates}: ${labels.notChecked}`, unsupported: `${labels.updates}: ${labels.unsupported}`, unauthorized: `${labels.updates}: ${labels.unauthorized}`, error: `${labels.updates}: ${labels.failed}`, stale: `${labels.updates}: ${labels.stale}`, unknown: `${labels.updates}: ${labels.unknownUpdate}` }[update.status] || `${labels.updates}: ${labels.unknownUpdate}`; const checked = update.checked_at ? ` · ${labels.checked}: ${new Date(update.checked_at).toLocaleString()}` : ""; const error = localizedUpdateError(update, labels); return `${status}${checked}${error && update.status !== "updates_available" ? ` · ${error}` : ""}`; }
function simulationEnabled(update) { return update?.dry_run_supported === true && (update?.status === "updates_available" || update?.status === "current") && update?.fresh === true && update?.authorized !== false; }
function simulationReason(update, labels) { if (update?.simulation_reason === "helper-unavailable") return labels.helperUnavailableReason; if (update?.simulation_reason === "target-not-running-or-not-checked") return labels.stoppedReason; if (update?.status === "unauthorized" || update?.authorized === false) return labels.unauthorizedReason; if (update?.status === "unsupported") return labels.unsupportedReason; if (update?.status === "stale" || update?.fresh === false) return labels.staleReason; if (update?.status === "not_checked" || !update?.status) return labels.notCheckedReason; if (update?.status === "current") return labels.noUpdatesReason; return labels.simulateDisabled; }
function resourceLines(item, labels) { return [bar(labels.memory, item.memory_used_bytes, item.memory_total_bytes), bar(labels.storage, item.disk_used_bytes, item.disk_total_bytes), item.memory_available_bytes != null ? metric(labels.availableMemory, bytes(item.memory_available_bytes)) : "", item.free_bytes != null ? metric(labels.freeStorage, bytes(item.free_bytes)) : ""].join(""); }
const css = `:host{display:block;color:var(--primary-text-color);box-sizing:border-box;container-type:inline-size}.card{background:var(--ha-card-background,var(--card-background-color));border-radius:var(--ha-card-border-radius,12px);padding:16px;box-shadow:var(--ha-card-box-shadow);overflow:visible;box-sizing:border-box}.header{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}.header h2{margin:0;font-size:1.25rem;min-width:0;overflow-wrap:anywhere}.status{display:inline-flex;align-items:center;gap:6px;font-size:.9em;flex:none}.dot{width:9px;height:9px;border-radius:50%;background:var(--success-color,#43a047)}.offline .dot{background:var(--error-color,#db4437)}.summary,.grid{display:grid;grid-template-columns:1fr;gap:8px}.metric,.item{border:1px solid var(--divider-color,#ddd);border-radius:8px;padding:10px;min-width:0}.metric strong{display:block;font-size:1.2em;overflow-wrap:anywhere}.muted{color:var(--secondary-text-color);font-size:.86em;overflow-wrap:anywhere}.section{margin-top:14px}.section h3{margin:0 0 8px;font-size:1rem}.item-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.item-head strong{min-width:0;overflow-wrap:anywhere}.bar-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:8px;align-items:center;margin-top:8px}.bar-row progress{width:100%;min-width:0}.pill{border-radius:12px;padding:2px 7px;font-size:.78em;background:var(--secondary-background-color);white-space:nowrap;flex:none;max-width:40%;overflow:hidden;text-overflow:ellipsis}.warning{color:var(--error-color,#db4437);overflow-wrap:anywhere}.readonly{color:var(--secondary-text-color);font-size:.82em;margin-top:10px}.action-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}.action-row button{flex:1 1 12rem;min-width:0}button.simulate,button.install,button.permission{padding:7px 10px;border:1px solid var(--primary-color,#03a9f4);border-radius:7px;background:var(--secondary-background-color);color:var(--primary-text-color);font:inherit;cursor:pointer}button.simulate:disabled,button.install:disabled,button.permission:disabled{opacity:.55;cursor:not-allowed;border-color:var(--divider-color,#777)}details{margin-top:8px}summary{cursor:pointer;list-style-position:inside;overflow-wrap:anywhere}@container (min-width:600px){.summary,.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@container (min-width:1000px){.summary,.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:420px){.card{padding:12px}.header{align-items:flex-start;flex-direction:column}.action-row{flex-direction:column}.action-row button{flex-basis:auto;width:100%}}`;
const editorCss = `:host{display:block;box-sizing:border-box;color:var(--primary-text-color)}.editor{display:grid;grid-template-columns:minmax(0,1fr);gap:12px;padding:4px 0;box-sizing:border-box;max-width:100%}.field{display:grid;grid-template-columns:minmax(0,8rem) minmax(0,1fr);align-items:center;gap:12px;min-width:0;line-height:1.35}.field.checkbox{grid-template-columns:auto minmax(0,1fr);justify-content:start;gap:10px;cursor:pointer}.field span{overflow-wrap:anywhere}.field input[type=text]{box-sizing:border-box;min-width:0;width:100%;max-width:100%;padding:8px 10px;border:1px solid var(--divider-color,#777);border-radius:6px;background:var(--ha-card-background,var(--card-background-color));color:var(--primary-text-color);font:inherit}.field input[type=checkbox]{width:20px;height:20px;margin:0;accent-color:var(--primary-color,#03a9f4)}@media(max-width:600px){.editor{gap:10px}.field,.field.checkbox{grid-template-columns:minmax(0,1fr);gap:6px}.field.checkbox{grid-template-columns:auto minmax(0,1fr);align-items:start}.field input[type=text]{font-size:16px;min-height:40px}}`;
const premiumCss = `.card{background:linear-gradient(145deg,var(--ha-card-background,var(--card-background-color)),color-mix(in srgb,var(--ha-card-background,var(--card-background-color)) 86%,var(--primary-color,#03a9f4)));border:1px solid color-mix(in srgb,var(--divider-color,#ddd) 70%,transparent);}.header{padding-bottom:4px}.status{padding:5px 9px;border-radius:999px;background:var(--secondary-background-color);}.status .dot{box-shadow:0 0 0 3px color-mix(in srgb,var(--success-color,#43a047) 18%,transparent)}.offline .status .dot{box-shadow:0 0 0 3px color-mix(in srgb,var(--error-color,#db4437) 18%,transparent)}.section{border-top:1px solid color-mix(in srgb,var(--divider-color,#ddd) 55%,transparent);padding-top:14px}.item{background:color-mix(in srgb,var(--card-background-color,#fff) 76%,transparent);transition:border-color .18s ease,background .18s ease}.item[open]{border-color:color-mix(in srgb,var(--primary-color,#03a9f4) 55%,var(--divider-color,#ddd));background:color-mix(in srgb,var(--primary-color,#03a9f4) 5%,var(--card-background-color,#fff))}.item>summary{list-style:none}.item>summary::-webkit-details-marker{display:none}.item-head{cursor:pointer;padding:0}.item-head::after{content:"+";color:var(--secondary-text-color);font-weight:700}.item[open]>.item-head::after{content:"−"}.item-body{padding-top:10px}.metric strong{font-variant-numeric:tabular-nums}@media(prefers-reduced-motion:reduce){.item{transition:none}}`;
const stableActionCss = `.action-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;align-items:stretch;margin-top:10px}.action-row button{width:100%;min-width:0;height:44px;min-height:44px;display:flex;align-items:center;justify-content:center;white-space:normal;overflow-wrap:anywhere;word-break:break-word}.vm-exclusion{margin:10px 0 0;padding:10px;border:1px solid var(--divider-color,#ddd);border-radius:8px;background:var(--secondary-background-color);overflow-wrap:anywhere}.simulation-result,.permission-result{margin-top:8px;min-width:0;overflow-wrap:anywhere}.simulation-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:6px}.simulation-summary strong{font-size:1.05em}.package-list{margin-top:8px}.package-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:4px 8px;padding:5px 0;border-top:1px solid var(--divider-color,#ddd);min-width:0}.package-name,.package-version{min-width:0;overflow-wrap:anywhere;word-break:break-word}@media(max-width:600px){.simulation-summary{grid-template-columns:1fr}.package-row{grid-template-columns:1fr}.action-row button{font-size:.92em}}`;
export class SmartHomelabMaintenanceCard extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: "open" }); this.config = { ...DEFAULTS }; this._items = { vm: new Map(), container: new Map() }; this._permissionOverrides = new Map(); this._permissionStates = new Map(); this._lastConfirmedPermissions = new Map(); this._updateSnapshots = new Map(); this._lastSize = null; this._resizeObserver = null; }
  connectedCallback() { this._ensureShell(); this._ensureRefreshButton(); this.shadowRoot.querySelector("style")?.append(stableActionCss); this.render(); this._observeSize(); }
  disconnectedCallback() { this._resizeObserver?.disconnect(); this._resizeObserver = null; }
  setConfig(config) { this.config = { ...DEFAULTS, ...(config && typeof config === "object" ? config : {}) }; this.render(); }
  set hass(value) { this._hass = value; this.render(); }
  get hass() { return this._hass; }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: "full", rows: "auto" }; }
  _observeSize() {
    if (this._resizeObserver || typeof ResizeObserver === "undefined") return;
    this._resizeObserver = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      const size = `${Math.round(width)}x${Math.round(height)}`;
      if (this._lastSize === null) { this._lastSize = size; return; }
      if (this._lastSize === size) return;
      this._lastSize = size;
      this.dispatchEvent(new CustomEvent("card-updated", { bubbles: true, composed: true }));
    });
    this._resizeObserver.observe(this);
  }
  _metric() { const node = document.createElement("div"); node.className = "metric"; node.innerHTML = '<span class="muted"></span><strong></strong><span class="muted"></span>'; return { node, label: node.children[0], value: node.children[1], sub: node.children[2] }; }
  _bar() { const node = document.createElement("div"); node.className = "bar-row"; node.innerHTML = '<span></span><progress max="100"></progress><span class="muted"></span>'; return { node, label: node.children[0], progress: node.children[1], value: node.children[2] }; }
  _section(titleKey, className = "section") { const section = document.createElement("div"); section.className = className; const heading = document.createElement("h3"); section.append(heading); const grid = document.createElement("div"); grid.className = "grid"; section.append(grid); return { section, heading, grid, titleKey }; }
  _ensureShell() {
    if (this._shell) return;
    this.shadowRoot.innerHTML = `<style>${css}${premiumCss}</style><section class="card"><div class="header"><h2></h2><span class="status" role="status"><i class="dot"></i><span></span></span></div><p class="warning" hidden></p><p class="compatibility muted" role="status"></p><div class="section overview"><h3></h3><div class="summary"></div></div><details class="section host-details" data-section="host"><summary><strong></strong></summary><div class="host-actions action-row"></div><div class="grid host-grid"></div></details><div class="section vm-section"><h3></h3><div class="grid vm-grid"></div><p class="muted empty-vms" hidden></p></div><div class="section container-section"><h3></h3><div class="grid container-grid"></div><p class="muted empty-containers" hidden></p></div><div class="section maintenance-section"><h3></h3><div class="summary maintenance-summary"></div><div class="readonly"></div></div></section>`;
    const root = this.shadowRoot; this._shell = { card: root.querySelector(".card"), title: root.querySelector(".header h2"), status: root.querySelector(".status"), statusText: root.querySelector(".status span"), warning: root.querySelector(".warning"), compatibility: root.querySelector(".compatibility"), overview: root.querySelector(".overview"), overviewTitle: root.querySelector(".overview h3"), overviewGrid: root.querySelector(".overview .summary"), host: root.querySelector(".host-details"), hostTitle: root.querySelector(".host-details summary strong"), hostActions: root.querySelector(".host-actions"), hostGrid: root.querySelector(".host-grid"), vm: this._sectionRefs("vm"), container: this._sectionRefs("container"), maintenance: this._sectionRefs("maintenance") };
    this._shell.hostButton = this._dryRunButton("host"); this._shell.hostActions.append(this._shell.hostButton); this._shell.hostUpdate = document.createElement("div"); this._shell.hostUpdate.className = "muted update-status"; this._shell.hostUpdate.hidden = true; this._shell.hostGrid.append(this._shell.hostUpdate);
    this._shell.overviewMetrics = ["host", "lastUpdated", "cpu", "memory", "storage"].map(() => this._metric()); this._shell.overviewMetrics.forEach((m) => this._shell.overviewGrid.append(m.node));
    this._shell.hostMetrics = ["version", "kernel", "uptime"].map(() => this._metric()); this._shell.hostMetrics.forEach((m) => this._shell.hostGrid.append(m.node)); this._shell.hostBars = [this._bar(), this._bar(), this._bar()]; this._shell.hostBars.forEach((b) => this._shell.hostGrid.append(b.node));
    this._shell.jobs = this._metric(); this._shell.maintenance.section.querySelector(".maintenance-summary").append(this._shell.jobs.node);
  }
  _sectionRefs(kind) { const section = this.shadowRoot.querySelector(`.${kind}-section`); return { section, heading: section.querySelector("h3"), grid: section.querySelector(`.${kind}-grid`), empty: section.querySelector(`.empty-${kind === "vm" ? "vms" : "containers"}`) }; }
  _setMetric(metricNode, label, value, sub = "") { metricNode.label.textContent = label; metricNode.value.textContent = value ?? "–"; metricNode.sub.textContent = sub; metricNode.sub.hidden = !sub; }
  _setBar(barNode, label, used, total, free, freeLabel) { const value = pct(used, total); barNode.node.hidden = value === null; if (value !== null) { barNode.label.textContent = label; barNode.progress.value = value; barNode.value.textContent = free != null ? `${value.toFixed(0)}% · ${freeLabel}: ${bytes(free)}` : `${value.toFixed(0)}%`; } }
  _item(kind, id) { const article = document.createElement("details"); article.className = "item"; article.dataset.itemId = String(id); const head = document.createElement("summary"); head.className = "item-head"; const strong = document.createElement("strong"); const pill = document.createElement("span"); pill.className = "pill"; head.append(strong, pill); const body = document.createElement("div"); body.className = "item-body"; article.append(head, body); const target = `${kind}:${id}`; const button = this._dryRunButton(target); const install = kind === "vm" ? null : this._installButton(target); const actions = document.createElement("div"); actions.className = "action-row"; actions.append(button); if (install) actions.append(install); body.append(actions); const permissionActions = document.createElement("div"); permissionActions.className = "action-row permission-row"; const permissionResult = document.createElement("div"); permissionResult.className = "muted permission-result"; permissionResult.setAttribute("role", "status"); permissionResult.hidden = true; const simulationPermission = kind === "vm" ? null : this._permissionButton(target, "simulation", permissionResult); const updatePermission = kind === "vm" ? null : this._permissionButton(target, "update", permissionResult); if (simulationPermission) permissionActions.append(simulationPermission); if (updatePermission) permissionActions.append(updatePermission); body.append(permissionActions, permissionResult); const bars = [this._bar(), this._bar(), this._bar()]; const updateText = document.createElement("div"); updateText.className = "muted"; body.append(updateText); const notice = document.createElement("p"); notice.className = "vm-exclusion"; notice.hidden = true; body.append(notice); const extra = document.createElement("div"); extra.className = "muted"; body.append(extra); bars.forEach((b) => body.append(b.node)); const refs = { article, strong, pill, actions, permissionActions, permissionResult, simulationPermission, updatePermission, bars, updateText, notice, button, install, extra }; this._items[kind].set(String(id), refs); return refs; }
  _updateItems(kind, items, labels, prefix) { const target = kind === "vm" ? this._shell.vm.grid : this._shell.container.grid; const seen = new Set(); const permissions = permissionText(resolveLanguage(this._hass)); [...items].sort((a, b) => Number(kind === "vm" ? a.vmid : a.container_id) - Number(kind === "vm" ? b.vmid : b.container_id)).forEach((item) => { const id = String(kind === "vm" ? item.vmid ?? item.entity_id : item.container_id ?? item.entity_id); let refs = this._items[kind].get(id); const isNew = !refs; if (!refs) refs = this._item(kind, id); seen.add(id); refs.strong.textContent = `${prefix} ${id} · ${item.name}`; refs.pill.textContent = item.running ? labels.running : labels.stopped; refs.article.ariaLabel = `${prefix} ${id} · ${item.name}`; this._setBar(refs.bars[0], labels.cpu, item.cpu_percent, 100); this._setBar(refs.bars[1], labels.memory, item.memory_used_bytes, item.memory_total_bytes, item.memory_available_bytes, labels.availableMemory); this._setBar(refs.bars[2], labels.storage, item.disk_used_bytes, item.disk_total_bytes, item.free_bytes, labels.freeStorage); const update = item.update === null ? { status: "not_checked" } : (item.update || {}); refs.updateText.textContent = kind === "vm" ? "" : updateText(update, labels); refs.updateText.hidden = kind === "vm" || !refs.updateText.textContent; const enabled = kind !== "vm" && simulationEnabled(update); const installEnabled = kind !== "vm" && update.update_supported === true && update.status === "updates_available" && update.fresh === true && Boolean(update.plan_digest); const eligible = kind === "container" && item.running === true && ["debian", "ubuntu"].includes(String(item.os_name || "").toLowerCase()) && String(item.package_manager || "").toLowerCase() === "apt"; const simulationAuthorized = update.simulation_authorized === true || update.authorized === true; const updateAuthorized = update.update_authorized === true; refs.actions.hidden = kind === "vm"; refs.permissionActions.hidden = !eligible; refs.button.textContent = labels.simulate; refs.button.hidden = false; refs.button.disabled = !enabled; refs.button.setAttribute("aria-disabled", String(!enabled)); refs.button.title = enabled ? "" : simulationReason(update, labels); if (refs.install) { refs.install._update = update; refs.install.disabled = !installEnabled; refs.install.hidden = false; refs.install.setAttribute("aria-disabled", String(!installEnabled)); refs.install.title = installEnabled ? "" : labels.installDisabled; } if (refs.simulationPermission) { refs.simulationPermission._permissions = { simulation_authorized: simulationAuthorized, update_authorized: updateAuthorized }; refs.simulationPermission.textContent = simulationAuthorized ? permissions.revokeSimulation : permissions.allowSimulation; refs.simulationPermission.setAttribute("aria-pressed", String(simulationAuthorized)); } if (refs.updatePermission) { refs.updatePermission._permissions = { simulation_authorized: simulationAuthorized, update_authorized: updateAuthorized }; refs.updatePermission.textContent = updateAuthorized ? permissions.revokeUpdates : permissions.allowUpdates; refs.updatePermission.setAttribute("aria-pressed", String(updateAuthorized)); refs.updatePermission.disabled = !simulationAuthorized && !updateAuthorized; } refs.notice.textContent = labels.vmExclusion; refs.notice.hidden = kind !== "vm"; const extra = [displayValue(item.os_name), displayValue(item.os_version)].filter(Boolean).join(" "); refs.extra.textContent = extra; refs.extra.hidden = !extra; if (isNew) target.append(refs.article); }); for (const [id, refs] of this._items[kind]) if (!seen.has(id)) { refs.article.remove(); this._items[kind].delete(id); } }
  render() {
    queueMicrotask(() => this._ensureInstallButtons(labelsFor(resolveLanguage(this._hass))));
    this._ensureShell(); this._ensureRefreshButton(); const labels = labelsFor(resolveLanguage(this._hass)); const data = model(this._hass, this.config); const host = data.host; const s = this._shell; s.refreshButton.textContent = labels.refresh; s.refreshButton.title = labels.refresh; const statusLabel = data.agentStatus === "connected" ? labels.connected : data.agentStatus === "error" ? labels.error : data.agentStatus === "offline" ? labels.offline : labels.unknown; const compatibilityLabel = data.compatibility === "current" ? labels.compatibilityCurrent : data.compatibility === "outdated" ? labels.compatibilityOutdated : data.compatibility === "incompatible" ? labels.compatibilityIncompatible : labels.compatibilityUnknown;
    s.card.classList.toggle("offline", !data.connected); s.card.ariaLabel = this.config.title; s.title.textContent = this.config.title; s.statusText.textContent = statusLabel; s.warning.hidden = !data.error; s.warning.textContent = data.error ? `${labels.error}: ${data.error}` : ""; s.compatibility.textContent = `${labels.compatibility}: ${compatibilityLabel}`; s.compatibility.dataset.status = data.compatibility; s.overviewTitle.textContent = labels.overview;
    this._setMetric(s.overviewMetrics[0], labels.host, host?.name || labels.noData, host?.online === false ? labels.hostOffline : host?.online === true ? labels.connected : labels.unknown); this._setMetric(s.overviewMetrics[1], labels.lastUpdated, data.lastUpdated ? new Date(data.lastUpdated).toLocaleString() : labels.noData); this._setMetric(s.overviewMetrics[2], labels.cpu, host?.cpu_percent != null ? `${Number(host.cpu_percent).toFixed(1)}%` : labels.noData, host?.cpu_cores ? `${host.cpu_cores} cores` : ""); this._setMetric(s.overviewMetrics[3], labels.memory, host?.memory_used_bytes != null ? bytes(host.memory_used_bytes) : labels.noData, host?.memory_total_bytes ? `of ${bytes(host.memory_total_bytes)}` : ""); this._setMetric(s.overviewMetrics[4], labels.storage, host?.storage_used_bytes != null ? bytes(host.storage_used_bytes) : labels.noData, host?.storage_total_bytes ? `of ${bytes(host.storage_total_bytes)}` : "");
    s.host.hidden = !host; s.hostTitle.textContent = host ? `${labels.host} · ${host.name}` : ""; const hostUpdate = host?.update || {}; const hostEnabled = simulationEnabled(hostUpdate); s.hostButton.textContent = labels.simulate; s.hostButton.hidden = false; s.hostButton.disabled = !hostEnabled; s.hostButton.setAttribute("aria-disabled", String(!hostEnabled)); s.hostButton.title = hostEnabled ? "" : simulationReason(hostUpdate, labels); s.hostUpdate.textContent = updateText(hostUpdate, labels); s.hostUpdate.hidden = !s.hostUpdate.textContent; this._setMetric(s.hostMetrics[0], labels.version, displayValue(host?.release)); this._setMetric(s.hostMetrics[1], labels.kernel, displayValue(host?.kernel)); this._setMetric(s.hostMetrics[2], labels.uptime, uptime(host?.uptime_seconds)); this._setBar(s.hostBars[0], labels.cpu, host?.cpu_percent, 100); this._setBar(s.hostBars[1], labels.memory, host?.memory_used_bytes, host?.memory_total_bytes, host?.memory_available_bytes, labels.availableMemory); this._setBar(s.hostBars[2], labels.storage, host?.storage_used_bytes, host?.storage_total_bytes, host?.storage_available_bytes, labels.freeStorage);
    s.vm.section.hidden = !this.config.show_vms; s.vm.heading.textContent = `${labels.vms} (${data.vms.length})`; this._updateItems("vm", data.vms, labels, "VM"); s.vm.empty.textContent = labels.noVms; s.vm.empty.hidden = data.vms.length !== 0; s.container.section.hidden = !this.config.show_containers; s.container.heading.textContent = `${labels.containers} (${data.containers.length})`; this._updateItems("container", data.containers, labels, "CT"); s.container.empty.textContent = labels.noContainers; s.container.empty.hidden = data.containers.length !== 0;
    s.maintenance.section.hidden = !this.config.show_maintenance; s.maintenance.heading.textContent = labels.maintenance; this._setMetric(s.jobs, labels.jobs, data.jobs === null ? null : data.jobs); const recoveryStatus = recoveryText(data.jobSummary, resolveLanguage(this._hass) === "de"); const readonly = s.maintenance.section.querySelector(".readonly"); readonly.textContent = recoveryStatus || labels.readOnly; readonly.title = data.jobSummary?.last_recovery_at ? `${labels.checked}: ${new Date(data.jobSummary.last_recovery_at).toLocaleString()}` : ""; this._ensureInstallButtons(labels);
  }
  _ensureInstallButtons(labels) {
    const add = (button) => {
      button.textContent = labels.install;
      const enabled = button._update?.update_supported === true;
      button.title = enabled ? "" : labels.installDisabled;
      button.setAttribute("aria-label", enabled ? labels.install : `${labels.install}: ${labels.installDisabled}`);
    };
    this.shadowRoot.querySelectorAll("button.install").forEach(add);
  }
  static getConfigElement() { return document.createElement("smart-homelab-maintenance-card-editor"); }
  static getStubConfig() { return { title: "Smart Homelab Maintenance", show_vms: true, show_containers: true }; }
}

function scrollDiagnosticForCard(card) {
  const style = (node) => {
    if (!node || node.nodeType !== Node.ELEMENT_NODE) return null;
    const computed = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return {
      tag: node.tagName.toLowerCase(), id: node.id || null, className: typeof node.className === "string" ? node.className : null,
      rect: { top: rect.top, bottom: rect.bottom, height: rect.height },
      clientHeight: node.clientHeight, scrollHeight: node.scrollHeight, scrollTop: node.scrollTop,
      overflowY: computed.overflowY, overflow: computed.overflow, height: computed.height,
      maxHeight: computed.maxHeight, position: computed.position, touchAction: computed.touchAction,
    };
  };
  const ancestors = [];
  let node = card;
  while (node && node.nodeType === Node.ELEMENT_NODE && ancestors.length < 12) {
    ancestors.push(style(node));
    node = node.parentElement;
  }
  const root = card.shadowRoot;
  const items = root ? [...root.querySelectorAll(".container-grid .item")] : [];
  const last = items.at(-1);
  let squareGridParent = card.parentElement;
  while (squareGridParent && squareGridParent !== document.body && squareGridParent.localName !== "hui-grid-card") squareGridParent = squareGridParent.parentElement;
  return {
    generatedAt: new Date().toISOString(),
    element: style(card),
    shadowRoot: root ? {
      host: style(card),
      card: style(root.querySelector(".card")),
      containerGrid: style(root.querySelector(".container-grid")),
      itemCount: items.length,
      lastItem: style(last),
    } : null,
    squareGridParent: squareGridParent ? { tag: squareGridParent.localName, square: squareGridParent.hasAttribute("square"), naturalHeightApplied: squareGridParent === card._naturalGridParent } : null,
    ancestors,
  };
}

// Read-only console probe for authenticated mobile/WebView diagnosis. It is
// intentionally opt-in and does not change layout, focus, or scroll position.
if (typeof window !== "undefined") {
  window.smartHomelabMaintenanceScrollDiagnostics = () =>
    [...document.querySelectorAll("smart-homelab-maintenance-card")].map(scrollDiagnosticForCard);
}
const originalUpdateItems = SmartHomelabMaintenanceCard.prototype._updateItems;
SmartHomelabMaintenanceCard.prototype._updateItems = function (kind, items, labels, prefix) {
  // Permission convergence and update freshness are independent per target.
  // A matching readback must never acknowledge the next not_checked refresh
  // for every other guest.
  const permissions = permissionText(resolveLanguage(this._hass));
  const normalized = items.map((item) => {
    const id = String(kind === "vm" ? item.vmid ?? item.entity_id : item.container_id ?? item.entity_id);
    const target = `${kind}:${id}`;
    const base = item.update === null ? { status: "not_checked" } : (item.update || {});
    const state = this._permissionStates.get(target);
    const hasPermissionFields = typeof base.simulation_authorized === "boolean" && typeof base.update_authorized === "boolean";
    if (hasPermissionFields) this._lastConfirmedPermissions.set(target, { simulation_authorized: base.simulation_authorized, update_authorized: base.update_authorized });
    if (hasPermissionFields && state?.expected && samePermissions(base, state.expected)) {
      this._permissionStates.set(target, { ...state, readback: { ...base }, status: "confirmed" });
      this._permissionOverrides.delete(target);
    } else if (hasPermissionFields && state?.status === "pending") {
      this._permissionStates.set(target, { ...state, readback: { ...base }, status: "stale" });
    }
    const snapshot = this._updateSnapshots.get(target);
    const persisted = base.dry_run;
    if (!snapshot && persisted?.success === true && persisted?.plan_digest) {
      this._updateSnapshots.set(target, { ...base, plan_digest: persisted.plan_digest, dry_run: persisted, historical: true });
    }
    const retainedSnapshot = this._updateSnapshots.get(target);
    const stale = ["not_checked", "unknown", "error", "unavailable"].includes(base.status) || base.fresh === false;
    // Historical data is display-only and cannot enable simulation/install.
    const update = retainedSnapshot && stale ? { ...base, historical_dry_run: retainedSnapshot, historical: true, fresh: false } : { ...base };
    return { ...item, __permissionSnapshot: Boolean(retainedSnapshot && stale), __permissionOverridePending: state?.status === "pending", __permissionOverride: state?.expected, update };
  });
  originalUpdateItems.call(this, kind, normalized, labels, prefix);
  normalized.forEach((item) => {
    const id = String(kind === "vm" ? item.vmid ?? item.entity_id : item.container_id ?? item.entity_id);
    const refs = this._items[kind].get(id);
    if (!refs || kind === "vm") return;
    const target = `${kind}:${id}`;
    const update = item.update || {};
    const localSimulation = this._updateSnapshots.get(target);
    const simulationVerified = Boolean(localSimulation?.dry_run?.success === true && localSimulation?.dry_run?.safe === true && localSimulation?.plan_digest === update.plan_digest);
    if (refs.install) {
      if (refs.install._attemptPlanDigest && refs.install._attemptPlanDigest !== update.plan_digest) {
        refs.install._attemptId = null;
        refs.install._attemptPlanDigest = null;
      }
      const safeToInstall = kind === "container" && update.update_supported === true && update.execution_enabled === true && update.backend_connected === true && update.status === "updates_available" && update.fresh === true && update.simulation_authorized === true && update.update_authorized === true && simulationVerified && update.job_conflict !== true && !(update.held_packages || []).length && !(update.conflicts || []).length && !(update.removals || []).length && Boolean(update.plan_digest);
      refs.install.disabled = !safeToInstall;
      refs.install.setAttribute("aria-disabled", String(!safeToInstall));
    }
    if (item.__permissionOverridePending && item.__permissionOverride) this._permissionOverrides.set(`${kind}:${id}`, { ...item.__permissionOverride });
    if (["updates_available", "current"].includes(update.status)) this._updateSnapshots.set(target, { ...update });
    if (refs.simulationPermission) {
      const known = this._lastConfirmedPermissions.get(target);
      const simulationAuthorized = typeof update.simulation_authorized === "boolean" ? update.simulation_authorized : known?.simulation_authorized === true;
      const updateAuthorized = typeof update.update_authorized === "boolean" ? update.update_authorized === true : known?.update_authorized === true;
      const permissionState = this._permissionStates.get(target);
      const pending = permissionState?.status === "pending" && permissionState.expected && !samePermissions(update, permissionState.expected);
      refs.simulationPermission._permissions = { simulation_authorized: simulationAuthorized, update_authorized: updateAuthorized };
      refs.permissionActions.dataset.state = pending ? "pending" : (["not_checked", "unknown", "error", "unavailable"].includes(update.status) ? "stale" : "confirmed");
      if (pending) {
        refs.simulationPermission.textContent = permissions.permissionPending;
        refs.simulationPermission.disabled = true;
        refs.simulationPermission.setAttribute("aria-busy", "true");
        if (refs.updatePermission) {
          refs.updatePermission.textContent = permissions.permissionPending;
          refs.updatePermission.disabled = true;
          refs.updatePermission.setAttribute("aria-busy", "true");
        }
        refs.permissionResult.hidden = false;
        refs.permissionResult.textContent = permissions.permissionPending;
        refs.permissionResult.classList.add("warning");
        refs.permissionResult.dataset.pending = "true";
      } else {
        refs.simulationPermission.textContent = simulationAuthorized ? permissions.revokeSimulation : permissions.allowSimulation;
        refs.simulationPermission.disabled = false;
        refs.simulationPermission.removeAttribute("aria-busy");
        if (refs.updatePermission) {
          refs.updatePermission.textContent = updateAuthorized ? permissions.revokeUpdates : permissions.allowUpdates;
          refs.updatePermission.disabled = !simulationAuthorized && !updateAuthorized;
          refs.updatePermission.removeAttribute("aria-busy");
        }
        if (permissionState?.status === "confirmed" && refs.permissionResult.dataset.pending === "true") {
          refs.permissionResult.hidden = false;
          refs.permissionResult.textContent = permissions.permissionSuccess;
          refs.permissionResult.classList.remove("warning");
          delete refs.permissionResult.dataset.pending;
        }
      }
    }
  });
};

SmartHomelabMaintenanceCard.prototype._renderJobStatus = function () {
  const data = model(this._hass, this.config);
  const labels = labelsFor(resolveLanguage(this._hass));
  const active = new Set(["queued", "preflight", "running", "verifying", "postcheck"]);
  const recoverable = new Set(["blocked", "manual_recovery_required", "recovery_pending", "recovery_blocked"]);
  for (const item of data.containers) {
    const id = String(item.container_id ?? item.entity_id);
    const refs = this._items.container.get(id);
    if (!refs) continue;
    const job = item.job;
    if (!job) { refs.jobText?.remove(); refs.jobActions?.remove(); delete refs.jobText; delete refs.jobActions; continue; }
    if (!refs.jobText) { refs.jobText = document.createElement("div"); refs.jobText.className = "muted job-status"; refs.jobText.setAttribute("role", "status"); refs.article.querySelector(".item-body").append(refs.jobText); }
    const phase = String(job.phase || job.state || "unknown");
    refs.jobText.textContent = `${active.has(job.state) ? labels.runningJob : job.state} · ${phase} · ${job.message || ""} · ${job.job_id}`;
    if (!refs.jobActions) { refs.jobActions = document.createElement("div"); refs.jobActions.className = "action-row job-actions"; refs.article.querySelector(".item-body").append(refs.jobActions); }
    refs.jobActions.replaceChildren();
    const detail = document.createElement("button"); detail.type = "button"; detail.textContent = labels.runningJob;
    detail.addEventListener("click", async (event) => { event.preventDefault(); event.stopPropagation(); try { const response = await this._hass.callService("smart_homelab_maintenance", "get_job", { job_id: job.job_id }, undefined, true, true); const payload = response?.response?.data || response?.data || response; refs.jobText.textContent = `${payload?.state || job.state} · ${payload?.phase || phase} · ${payload?.message || job.message || ""} · ${job.job_id}`; } catch (error) { refs.jobText.textContent = `${labels.error}: ${error?.message || "job details unavailable"}`; } });
    refs.jobActions.append(detail);
    if (recoverable.has(job.state)) {
      const repair = document.createElement("button"); repair.type = "button"; repair.textContent = labels.repairCheck;
      repair.addEventListener("click", async (event) => {
        event.preventDefault(); event.stopPropagation(); repair.disabled = true;
        try {
          const response = await this._hass.callService("smart_homelab_maintenance", "repair_check", { job_id: job.job_id }, undefined, true, true);
          const result = response?.response?.data || response?.data || response;
          const inspection = result?.inspection || {};
          if (inspection.repairable === true) {
            const perform = document.createElement("button"); perform.type = "button"; perform.textContent = labels.repair;
            perform.addEventListener("click", async (repairEvent) => {
              repairEvent.preventDefault(); repairEvent.stopPropagation(); perform.disabled = true;
              try {
                if (typeof window !== "undefined" && typeof window.confirm === "function" && !window.confirm(`${labels.repair}?`)) return;
                await this._hass.callService("smart_homelab_maintenance", "repair", { job_id: job.job_id, confirm: true }, undefined, true, true);
                refs.jobText.textContent = `${labels.repair}: ${job.job_id}`;
                perform.remove();
              } catch (error) { refs.jobText.textContent = `${labels.error}: ${error?.message || "repair failed"}`; }
              finally { perform.disabled = false; }
            });
            repair.replaceWith(perform);
          } else {
            refs.jobText.textContent = `${labels.error}: ${inspection.reason || "repair is not safe"}`;
          }
        } catch (error) { refs.jobText.textContent = `${labels.error}: ${error?.message || "repair inspection failed"}`; }
        finally { repair.disabled = false; }
      });
      refs.jobActions.append(repair);
    }
  }
};
const originalCardRender = SmartHomelabMaintenanceCard.prototype.render;
SmartHomelabMaintenanceCard.prototype.render = function () { originalCardRender.call(this); this._renderJobStatus(); };

export class SmartHomelabMaintenanceCardEditor extends HTMLElement {
  constructor() { super(); this.config = { ...DEFAULTS }; this._rendered = false; this._hass = undefined; }
  set hass(value) { this._hass = value; this.render(); }
  get hass() { return this._hass; }
  setConfig(config) { this.config = { ...DEFAULTS, ...(config && typeof config === "object" ? config : {}) }; this.render(); }
  render() {
    if (!this._rendered) {
      this.innerHTML = `<style>${editorCss}</style><div class="editor"><label class="field"><span data-label="title"></span><input data-field="title" type="text"></label><label class="field checkbox"><input data-field="show_vms" type="checkbox"><span data-label="vms"></span></label><label class="field checkbox"><input data-field="show_containers" type="checkbox"><span data-label="containers"></span></label><label class="field checkbox"><input data-field="show_maintenance" type="checkbox"><span data-label="maintenance"></span></label></div>`;
      this.addEventListener("change", (event) => {
        if (!(event.target instanceof HTMLInputElement)) return;
        const next = { ...this.config, title: this.querySelector('[data-field="title"]').value, show_vms: this.querySelector('[data-field="show_vms"]').checked, show_containers: this.querySelector('[data-field="show_containers"]').checked, show_maintenance: this.querySelector('[data-field="show_maintenance"]').checked };
        this.config = next;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: next }, bubbles: true, composed: true }));
      });
      this._rendered = true;
    }
    const labels = editorText(resolveLanguage(this._hass));
    for (const field of ["title", "vms", "containers", "maintenance"]) this.querySelector(`[data-label="${field}"]`).textContent = labels[field];
    const title = this.querySelector('[data-field="title"]');
    if (title && !title.matches(":focus")) title.value = this.config.title;
    for (const field of ["show_vms", "show_containers", "show_maintenance"]) {
      const input = this.querySelector(`[data-field="${field}"]`);
      if (input && !input.matches(":focus")) input.checked = Boolean(this.config[field]);
    }
  }
}
const DRY_RUN_TIMEOUT_MS = 12000;
function dryRunData(response) {
  const payload = response?.response ?? response;
  return payload?.data && typeof payload.data === "object" ? payload.data : payload;
}
function localizedDryRunError(message, german = true) {
  const raw = String(message || "").toLowerCase();
  if (raw.includes("not authorized") || raw.includes("unauthorized")) return german ? "Ziel ist nicht autorisiert." : "Target is not authorized.";
  if (raw.includes("not supported") || raw.includes("unsupported")) return german ? "Ziel wird nicht unterstützt." : "Target is not supported.";
  if (raw.includes("timeout") || raw.includes("timed out")) return german ? "Zeitüberschreitung bei der Simulation." : "Simulation timed out.";
  return message || (german ? "unbekannter Fehler" : "unknown error");
}
function dryRunSummary(response, german = true) {
  const data = dryRunData(response);
  if (!data || typeof data !== "object") throw new Error("Die Serviceantwort ist leer oder ungültig.");
  const packages = Array.isArray(data.packages) ? data.packages : [];
  const warnings = [
    ...(Array.isArray(data.held_packages) ? data.held_packages.map((name) => `zurückgehalten: ${name}`) : []),
    ...(Array.isArray(data.conflicts) ? data.conflicts.map((item) => `Konflikt: ${item}`) : []),
    ...(Array.isArray(data.removals) ? data.removals.map((name) => `Entfernung: ${name}`) : []),
  ];
  const packageText = packages.length ? packages.map((item) => `${item.name || "?"} ${item.installed_version || "?"} → ${item.available_version || "?"}`).join(", ") : (german ? "keine Paketänderungen" : "no package changes");
  const safety = data.safe === true ? (german ? "Sicherheitsprüfung: bestanden" : "Safety assessment: passed") : (german ? "Sicherheitsprüfung: Warnung" : "Safety assessment: warning");
  const status = data.success === false ? `${german ? "Simulation fehlgeschlagen" : "Simulation failed"}: ${localizedDryRunError(data.error, german)}` : `${german ? "Simulation erfolgreich" : "Simulation successful"} · ${packages.length} ${german ? "Paketänderung(en)" : "package change(s)"}`;
  return `${status}. ${safety}. ${german ? "Pakete" : "Packages"}: ${packageText}.${warnings.length ? ` ${german ? "Warnungen" : "Warnings"}: ${warnings.join("; ")}.` : ""}`;
}
function renderDryRunResult(result, response, german) {
  const data = dryRunData(response);
  if (!data || typeof data !== "object") throw new Error("Die Serviceantwort ist leer oder ungültig.");
  result.replaceChildren();
  const summary = document.createElement("div");
  summary.className = "simulation-summary";
  const status = document.createElement("strong");
  status.textContent = data?.success === false ? (german ? "Simulation fehlgeschlagen" : "Simulation failed") : (german ? "Simulation erfolgreich" : "Simulation successful");
  const safety = document.createElement("span");
  safety.textContent = data?.safe === true ? (german ? "Sicherheitsprüfung: bestanden" : "Safety: passed") : (german ? "Sicherheitsprüfung: Warnung" : "Safety: warning");
  summary.append(status, safety);
  const count = document.createElement("span");
  const packages = Array.isArray(data?.packages) ? data.packages : [];
  count.textContent = `${packages.length} ${german ? "Paketänderung(en)" : "package change(s)"}`;
  summary.append(count);
  result.append(summary);
  if (data?.success === false) {
    const error = document.createElement("div");
    error.className = "warning";
    error.textContent = localizedDryRunError(data.error, german);
    result.append(error);
  }
  if (packages.length) {
    const details = document.createElement("details");
    details.className = "package-list";
    const heading = document.createElement("summary");
    heading.textContent = german ? "Paketdetails anzeigen" : "Show package details";
    details.append(heading);
    for (const item of packages) {
      const row = document.createElement("div");
      row.className = "package-row";
      const name = document.createElement("span");
      name.className = "package-name";
      name.textContent = String(item.name || "?");
      const version = document.createElement("span");
      version.className = "package-version";
      version.textContent = ` ${item.installed_version || "?"} → ${item.available_version || "?"}`;
      row.append(name, version);
      details.append(row);
    }
    result.append(details);
  }
  if (data?.safe !== true && data?.success !== false) result.classList.add("warning");
}
function permissionResponseError(response) {
  const candidates = [response, response?.response, response?.data, response?.response?.data];
  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== "object") continue;
    if (candidate.error) return typeof candidate.error === "string" ? candidate.error : candidate.error.message || "permission request failed";
    if (candidate.success === false) return candidate.message || "permission request failed";
  }
  return null;
}
function permissionResponseData(response) {
  const candidates = [response?.response?.data, response?.data, response?.response, response];
  return candidates.find((candidate) => candidate && typeof candidate === "object" && typeof candidate.simulation_authorized === "boolean" && typeof candidate.update_authorized === "boolean") || null;
}
function samePermissions(left, right) {
  return Boolean(left && right) && left.simulation_authorized === right.simulation_authorized && left.update_authorized === right.update_authorized;
}
SmartHomelabMaintenanceCard.prototype._permissionButton = function (target, permission, result) {
  const button = document.createElement("button");
  button.className = "permission";
  button.type = "button";
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    const german = resolveLanguage(this._hass) === "de";
    const labels = permissionText(german ? "de" : "en");
    const current = button._permissions || { simulation_authorized: false, update_authorized: false };
    const next = permission === "simulation"
      ? { simulation_authorized: !current.simulation_authorized, update_authorized: current.simulation_authorized ? false : current.update_authorized }
      : { simulation_authorized: true, update_authorized: !current.update_authorized };
    if (typeof window !== "undefined" && typeof window.confirm === "function" && !window.confirm(labels.permissionConfirm)) return;
    result.hidden = false;
    result.classList.remove("warning");
    result.textContent = labels.permissionRunning;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    let timer;
    try {
      const call = this._hass?.callService?.("smart_homelab_maintenance", "set_permissions", { target, confirm: true, ...next }, undefined, true, true);
      if (!call || typeof call.then !== "function") throw new Error(labels.permissionFailed);
      const timeout = typeof globalThis !== "undefined" && Number.isFinite(globalThis.__SMART_HOMELAB_PERMISSION_TIMEOUT_MS__)
        ? globalThis.__SMART_HOMELAB_PERMISSION_TIMEOUT_MS__ : 30000;
      const response = await Promise.race([
        call,
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(german ? "Zeitüberschreitung bei der Berechtigungsänderung." : "Permission change timed out.")), timeout); }),
      ]);
      const responseError = permissionResponseError(response);
      if (responseError) throw new Error(responseError);
      const readback = permissionResponseData(response);
      if (!samePermissions(readback, next)) throw new Error(labels.permissionReadbackFailed);
      this._permissionOverrides.set(target, { ...readback });
      const previous = this._permissionStates.get(target);
      this._permissionStates.set(target, { expected: { ...readback }, readback: { ...readback }, status: "pending", generation: (previous?.generation || 0) + 1 });
      this.render();
      result.textContent = labels.permissionPending;
      result.classList.add("warning");
      result.dataset.pending = "true";
      // The set_permissions service refreshes HA before this handler receives
      // its response. Trigger one additional read-only coordinator refresh
      // after the pending generation exists, so the next HA state can confirm
      // convergence instead of leaving the card on the pre-write snapshot.
      try {
        const refresh = this._hass?.callService?.("smart_homelab_maintenance", "check", {}, undefined, true, true);
        if (refresh && typeof refresh.then === "function") {
          const refreshTimeout = typeof globalThis !== "undefined" && Number.isFinite(globalThis.__SMART_HOMELAB_PERMISSION_REFRESH_TIMEOUT_MS__)
            ? globalThis.__SMART_HOMELAB_PERMISSION_REFRESH_TIMEOUT_MS__ : 12000;
          await Promise.race([
            refresh,
            new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("permission readback refresh timed out")), refreshTimeout); }),
          ]);
        }
      } catch (_) {
        // Keep the pending state fail-closed; a missing HA convergence must
        // never be reported as a confirmed permission change.
      }
    } catch (error) {
      result.textContent = `${labels.permissionFailed}: ${error?.message || "unknown error"}`;
      result.classList.add("warning");
      button.title = result.textContent;
    } finally {
      clearTimeout(timer);
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  });
  return button;
};
SmartHomelabMaintenanceCard.prototype._installButton = function (target) {
  const button = document.createElement("button");
  button.className = "install";
  button.type = "button";
  button.disabled = true;
  button.textContent = "Install updates";
  button.setAttribute("aria-disabled", "true");
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    const update = button._update || {};
    const german = resolveLanguage(this._hass) === "de";
    const labels = textFor(german ? "de" : "en");
    const packages = Array.isArray(update.packages) ? update.packages : [];
    const packageSummary = packages.length
      ? packages.map((item) => `${item.name || "?"} ${item.installed_version || "?"} → ${item.available_version || "?"}`).join(", ")
      : (german ? "keine Paketänderungen" : "no package changes");
    const risks = update.removals?.length || update.conflicts?.length || update.held_packages?.length
      ? (german ? "Warnungen: zurückgehaltene, konfliktbehaftete oder zu entfernende Pakete." : "Warnings: held, conflicting, or removing packages.")
      : (german ? "Keine Paketentfernungen/Konflikte; möglicher Neustartbedarf der Dienste bleibt bestehen." : "No removals/conflicts; services may still require a restart.");
    const confirmation = german
      ? `Ziel: ${target}\nPakete (${packages.length}): ${packageSummary}\nRisiken: ${risks}\nNeustartbedarf: möglicherweise.\n\nDieses konkrete Update jetzt installieren?`
      : `Target: ${target}\nPackages (${packages.length}): ${packageSummary}\nRisks: ${risks}\nRestart need: possible.\n\nInstall this exact update now?`;
    if (typeof window !== "undefined" && typeof window.confirm === "function" && !window.confirm(confirmation)) return;
    if (button._attemptPlanDigest !== update.plan_digest || !button._attemptId) {
      button._attemptPlanDigest = update.plan_digest;
      button._attemptId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }
    const attemptId = button._attemptId;
    const result = button._updateResult || document.createElement("div");
    result.className = "muted simulation-result";
    result.setAttribute("role", "status");
    if (!button._updateResult) { button._updateResult = result; (button.closest(".action-row") || button).after(result); }
    result.textContent = german ? "Update läuft …" : "Update running …";
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    let timer;
    try {
      const call = this._hass?.callService?.("smart_homelab_maintenance", "execute", { target, confirm: true, install_confirmed: true, plan_digest: update.plan_digest, attempt_id: attemptId }, undefined, true, true);
      if (!call || typeof call.then !== "function") throw new Error(german ? "Home Assistant hat keine Serviceantwort geliefert." : "Home Assistant returned no service response.");
      const response = await Promise.race([
        call,
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(german ? "Zeitüberschreitung beim Update." : "Update timed out.")), 30000); }),
      ]);
      const data = dryRunData(response);
      if (!data || data.success !== true) throw new Error(data?.error || (german ? "Update fehlgeschlagen." : "Update failed."));
      result.textContent = data.job_id ? `${german ? "Update erfolgreich abgeschlossen." : "Update completed successfully."} (${data.job_id})` : (german ? "Update erfolgreich abgeschlossen." : "Update completed successfully.");
      result.classList.remove("warning");
      button._attemptId = null;
    } catch (error) {
      result.textContent = `${german ? "Update fehlgeschlagen" : "Update failed"}: ${error?.message || (german ? "unbekannter Fehler" : "unknown error")}`;
      result.classList.add("warning");
    } finally {
      clearTimeout(timer);
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  });
  return button;
};
SmartHomelabMaintenanceCard.prototype._ensureRefreshButton = function () {
  if (this._refreshButton || !this._shell) return;
  const button = document.createElement("button");
  button.className = "refresh";
  button.type = "button";
  button.addEventListener("click", async (event) => {
    event.preventDefault(); event.stopPropagation();
    const german = resolveLanguage(this._hass) === "de";
    button.disabled = true; button.setAttribute("aria-busy", "true");
    try {
      const call = this._hass?.callService?.("smart_homelab_maintenance", "refresh", {}, undefined, true, true);
      if (!call || typeof call.then !== "function") throw new Error(german ? "Home Assistant hat keine Serviceantwort geliefert." : "Home Assistant returned no service response.");
      await call;
    } catch (error) {
      button.title = `${german ? "Prüfung fehlgeschlagen" : "Refresh failed"}: ${error?.message || "unknown error"}`;
    } finally { button.disabled = false; button.removeAttribute("aria-busy"); }
  });
  this._shell.card.querySelector(".header").append(button);
  this._refreshButton = button;
  this._shell.refreshButton = button;
};
SmartHomelabMaintenanceCard.prototype._dryRunButton = function (target) {
  const button = document.createElement("button");
  button.className = "simulate";
  button.type = "button";
  button.hidden = true;
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    const result = button._simulationResult || document.createElement("div");
    result.className = "muted simulation-result";
    result.setAttribute("role", "status");
    if (!button._simulationResult) { button._simulationResult = result; (button.closest(".action-row") || button).after(result); }
    result.replaceChildren();
    result.textContent = resolveLanguage(this._hass) === "de" ? "Simulation läuft …" : "Simulation running …";
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    let timer;
    try {
      const call = this._hass?.callService?.("smart_homelab_maintenance", "dry_run", { target, confirm: true }, undefined, true, true);
      if (!call || typeof call.then !== "function") throw new Error("Home Assistant hat keine Serviceantwort geliefert.");
      const response = await Promise.race([
        call,
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("Zeitüberschreitung bei der Simulation.")), Number(globalThis.__SMART_HOMELAB_DRY_RUN_TIMEOUT_MS__) || DRY_RUN_TIMEOUT_MS); }),
      ]);
      renderDryRunResult(result, response, resolveLanguage(this._hass) === "de");
      const data = dryRunData(response);
      if (data?.success === true && data?.safe === true && target.startsWith("container:")) {
        const current = button._update || {};
        this._updateSnapshots.set(target, {
          ...current,
          status: Array.isArray(data.packages) && data.packages.length ? "updates_available" : "current",
          available_count: Array.isArray(data.packages) ? data.packages.length : current.available_count,
          packages: data.packages || current.packages,
          plan_digest: data.plan_digest || current.plan_digest,
          fresh: true,
          dry_run: data,
        });
      }
      result.classList.toggle("warning", Boolean(dryRunData(response)?.success === false || dryRunData(response)?.safe === false));
    } catch (error) {
      result.textContent = `Simulation fehlgeschlagen: ${localizedDryRunError(error?.message || "unbekannter Servicefehler", resolveLanguage(this._hass) === "de")}`;
      result.classList.add("warning");
    } finally {
      clearTimeout(timer);
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  });
  return button;
};
if (!customElements.get("smart-homelab-maintenance-card")) customElements.define("smart-homelab-maintenance-card", SmartHomelabMaintenanceCard);
if (!customElements.get("smart-homelab-maintenance-card-editor")) customElements.define("smart-homelab-maintenance-card-editor", SmartHomelabMaintenanceCardEditor);
if (typeof window !== "undefined") { window.customCards = window.customCards || []; if (!window.customCards.some((entry) => entry.type === "smart-homelab-maintenance-card")) window.customCards.push({ type: "smart-homelab-maintenance-card", name: "Smart Homelab Maintenance", description: "Read-only Proxmox host, VM and LXC overview" }); }
