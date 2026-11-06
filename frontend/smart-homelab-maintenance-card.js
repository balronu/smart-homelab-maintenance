import { editorConfigChanged, labels, modelFromHass, normalizeConfig, phaseLabel, preserveSelection, progressFor, updateLabel } from "./card-state.js";

const css = `
:host { display:block; color:var(--primary-text-color); }
.card { background:var(--ha-card-background, var(--card-background-color)); border-radius:var(--ha-card-border-radius,12px); padding:16px; box-shadow:var(--ha-card-box-shadow); overflow:hidden; }
.header { display:flex; justify-content:space-between; gap:12px; align-items:center; margin-bottom:12px; }
.status { display:inline-flex; align-items:center; gap:6px; font-size:.9em; }
.dot { width:9px; height:9px; border-radius:50%; background:var(--success-color,#43a047); } .offline .dot { background:var(--error-color,#db4437); }
.summary, .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px; }
.metric, .container, .job { border:1px solid var(--divider-color,#ddd); border-radius:8px; padding:10px; min-width:0; }
.metric strong { display:block; font-size:1.35em; } .muted { color:var(--secondary-text-color); font-size:.86em; }
details { margin-top:8px; } summary { cursor:pointer; list-style-position:inside; } .app { display:flex; justify-content:space-between; gap:8px; border-top:1px solid var(--divider-color,#ddd); padding:7px 0; overflow-wrap:anywhere; }
.pill { border-radius:12px; padding:2px 7px; font-size:.78em; background:var(--secondary-background-color); } .blocked { color:var(--error-color,#db4437); }
.job-head { display:flex; justify-content:space-between; gap:8px; } progress { width:100%; margin-top:8px; } button { color:var(--primary-text-color); background:var(--secondary-background-color); border:1px solid var(--divider-color); border-radius:6px; padding:5px 8px; }
@media (max-width:420px) { .card { padding:12px; } .summary, .grid { grid-template-columns:1fr; } .header { align-items:flex-start; flex-direction:column; } }
`;

function esc(value) { return String(value ?? "").replace(/[&<>\"]/g, (c) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;" }[c])); }

export class SmartHomelabMaintenanceCard extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: "open" }); this.config = normalizeConfig(); this.openContainers = new Set(); this.selectedJob = null; }
  setConfig(config) { if (!config || typeof config !== "object") throw new Error("Card configuration must be an object"); this.config = normalizeConfig(config); this.render(); }
  set hass(value) { this._hass = value; const model = modelFromHass(value, this.config); this.selectedJob = preserveSelection({ selectedJob: this.selectedJob }, model); this.render(model); }
  get hass() { return this._hass; }
  render(model = modelFromHass(this._hass || {}, this.config)) {
    const text = labels(this._hass?.locale || "de");
    this.shadowRoot.innerHTML = `<style>${css}</style><section class="card ${model.connected ? "" : "offline"}" aria-label="${esc(this.config.title)}">
      <div class="header"><h2>${esc(this.config.title)}</h2><span class="status"><i class="dot"></i>${model.connected ? text.connected : text.offline}</span></div>
      ${model.error ? `<p class="blocked">${esc(model.error)}</p>` : ""}
      <div class="summary"><div class="metric"><span class="muted">${text.containers}</span><strong>${model.containers.length}</strong></div><div class="metric"><span class="muted">${text.updates}</span><strong>${model.updates}</strong></div><div class="metric"><span class="muted">${text.blocked}</span><strong>${model.blocked}</strong></div><div class="metric"><span class="muted">${text.jobs}</span><strong>${model.jobs.length}</strong></div></div>
      <div class="grid">${model.containers.map((container) => this.renderContainer(container)).join("")}</div>
      ${this.config.show_jobs ? this.renderJobs(model.jobs, text) : ""}
    </section>`;
    this.shadowRoot.querySelectorAll("details[data-container]").forEach((node) => { node.open = this.openContainers.has(node.dataset.container); node.addEventListener("toggle", () => node.open ? this.openContainers.add(node.dataset.container) : this.openContainers.delete(node.dataset.container)); });
    this.shadowRoot.querySelectorAll("button[data-job]").forEach((button) => button.addEventListener("click", () => { this.selectedJob = button.dataset.job; this.render(); }));
  }
  renderContainer(container) {
    const apps = (container.applications || []).map((app) => `<div class="app"><span>${esc(app.display_name || app.app_id)}<br><span class="muted">${esc(app.installed_version || "Version unbekannt")}</span></span><span class="pill ${app.blocked_reasons?.length ? "blocked" : ""}">${esc(updateLabel(app))}</span></div>`).join("");
    return `<details class="container" data-container="${esc(container.container_id)}"><summary><strong>CT ${esc(container.container_id)} · ${esc(container.name)}</strong><span class="muted"> ${container.running ? "running" : "stopped"}</span></summary><p class="muted">${esc(container.os_name || "OS unbekannt")} ${esc(container.os_version || "")}</p>${this.config.show_resources ? `<p class="muted">Ressourcen: ${esc(container.resource_status || "unbekannt")}</p>` : ""}${apps || `<p class="muted">Keine Anwendungen erkannt</p>`}</details>`;
  }
  renderJobs(jobs, text) {
    return `<h3>${text.jobsTitle}</h3><div class="grid">${jobs.length ? jobs.map((job) => { const progress = progressFor(job); return `<article class="job"><div class="job-head"><strong>${esc(job.target || "unknown")}</strong><button data-job="${esc(job.job_id)}">Details</button></div><div class="muted">${esc(phaseLabel(job))} · ${esc(job.state || "unknown")}</div>${progress === null ? `<div class="muted">Phase: ${esc(phaseLabel(job))}</div>` : `<progress max="100" value="${progress}"></progress>`}<div class="muted">${esc(job.message || job.error_message || "")}</div>${this.selectedJob === job.job_id && job.events ? `<pre>${esc(job.events.map((event) => event.message).join("\n"))}</pre>` : ""}</article>`; }).join("") : `<p class="muted">${text.noJobs}</p>`}</div>`;
  }
  static getConfigElement() { return document.createElement("smart-homelab-maintenance-card-editor"); }
  static getStubConfig() { return { title: "Smart Homelab Maintenance", show_jobs: true }; }
}

export class SmartHomelabMaintenanceCardEditor extends HTMLElement {
  setConfig(config) { this.config = normalizeConfig(config); this.render(); }
  render() { this.innerHTML = `<label>Titel <input value="${esc(this.config.title)}"></label><label><input type="checkbox" ${this.config.show_jobs ? "checked" : ""}> Jobhistorie</label>`; this.querySelectorAll("input").forEach((input) => input.addEventListener("change", () => { const next = { ...this.config, title: this.querySelector("input").value, show_jobs: this.querySelectorAll("input")[1].checked }; if (editorConfigChanged(this.config, next)) this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: next }, bubbles: true, composed: true })); })); }
}

if (!customElements.get("smart-homelab-maintenance-card")) customElements.define("smart-homelab-maintenance-card", SmartHomelabMaintenanceCard);
if (!customElements.get("smart-homelab-maintenance-card-editor")) customElements.define("smart-homelab-maintenance-card-editor", SmartHomelabMaintenanceCardEditor);
if (typeof window !== "undefined") {
  window.customCards = window.customCards || [];
  if (!window.customCards.some((entry) => entry.type === "smart-homelab-maintenance-card")) window.customCards.push({ type: "smart-homelab-maintenance-card", name: "Smart Homelab Maintenance", description: "Offline-safe homelab maintenance overview" });
}
