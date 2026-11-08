# Stable-Abnahme / Stable acceptance

## Phase 35 automation boundary

- [ ] The versioned policy is deployed with `discover_only` as its default.
- [ ] `auto_eligible` is enabled only through an explicit onboarding action.
- [ ] Discovery evidence is fresh, bounded, and obtained through the fixed
      read-only transport; no free shell or VM transport is present.
- [ ] The serialized allowlist plan is reviewed before any production apply.
- [ ] Helper/socket deployment, HA onboarding, health reporting, migration,
      and rollback are tested end-to-end. These remain open for Phase 36.
- [ ] Phase-36 discovery service is installed only through the official
      installer and passes peer-UID, fixed-command, timeout, output-limit,
      recovery, and idempotency tests in an isolated environment.
- [ ] The orchestration status API and HA policy selector preserve
      `discover_only` on migration and never enable real package actions.
- [ ] Isolated Phase-37 end-to-end acceptance passes for first install,
      repeat install, upgrade/recovery, dynamic container events, VM blocking,
      audit, rollback, API status, and HA options migration.
- [ ] Phase-39 real installer acceptance passes on an ephemeral root/systemd
      CI runner; a skipped or unsupported runner is NOT RUN, not PASS.
- [ ] Productive Proxmox/HA live wiring remains separately approved and tested;
      CI does not authorize helper or allowlist activation on `pve-home`.

Diese Checkliste ist ein Prüfvertrag für eine spätere Stable-Freigabe. Sie
ist keine Installations- oder Aktivierungsfreigabe. Jede Zeile benötigt einen
nachvollziehbaren PASS, BLOCKED oder NOT RUN-Nachweis; ein fehlender Nachweis
ist kein PASS.

## Deutsch

### Quelle und Installation

- [ ] Exakter Stable-Tag, Commit, Manifest, Agent-Version und API-Vertrag 1.1
      stimmen überein.
- [ ] HACS-Installation der Integration und separater Proxmox-Agent sind als
      zwei unabhängige Vorgänge dokumentiert.
- [ ] TLS-Zertifikat, SAN, vertrauenswürdige CA und private HTTPS-Adresse sind
      geprüft; kein HTTP-Fallback und kein `verify=False`.
- [ ] Offizieller Agent-Updater ist ohne Apply vorgeprüft; Apply, Neustart und
      Rollback sind separat freigegeben und anhand des tatsächlichen Commits
      nachvollziehbar.

### Betrieb und Inventar

- [ ] Agent-Health, API 1.1, systemd-Dienst, Cgroup, Port 48128 und Port 8128
      sind geprüft.
- [ ] Host, VMs und LXCs werden angezeigt; gestoppte Gäste werden nicht
      gestartet.
- [ ] VM-Karten zeigen Name, Laufstatus und Ressourcen. VMs bleiben dauerhaft
      Monitoring-only: keine Paketprüfung, Simulation oder Installation.
- [ ] LXC-Eignung weist laufenden Zustand, unterstütztes OS/Paketmanager und
      explizite Zielautorisierung nach; keine automatische Allowlist/Helper-
      Aktivierung.
- [ ] Für alle neun laufenden Debian-/APT-LXCs existiert eine geprüfte
      Einzel-Abnahme mit Read-/Simulations-, Negativ- und Abbruchnachweis;
      CT112 bleibt gestoppt und ausgeschlossen.

### Simulation und Sicherheit

- [ ] Host-Simulation bleibt read-only, nutzt einen frischen kanonischen Plan
      sowie TLS-/Sicherheitsprüfung und kann keine Installation auslösen.
- [ ] Autorisierte LXC-Simulation nutzt ausschließlich feste, geprüfte
      Operationen mit Zielvalidierung, Timeout und Concurrency-Schutz.
- [ ] VM-IDs erreichen weder `pct exec` noch einen anderen Update-Runner.
- [ ] Installationsbutton und allgemeiner Ausführungspfad bleiben deaktiviert;
      Paketinstallationen sind nicht unterstützt.
- [ ] Fehler, stale-Pläne, fehlende Berechtigungen, Rollback und Diagnose-
      informationen sind isoliert getestet.

### UI, Dokumentation und Release-Hygiene

- [ ] iPhone, iPad Hoch-/Querformat und Desktop zeigen keine Überläufe;
      Paketdetails, Lade-, Fehler- und Erfolgszustände bleiben stabil.
- [ ] README, Installationsanleitung, Changelog und DE/EN-Release-Notes
      beschreiben dieselben Grenzen.
- [ ] PR-Head, alle neun CI-Gates, Tag, Release-Flags und Artefakte sind auf
      demselben Commit verifiziert.
- [ ] Keine alten Beta-Releases oder Tags werden im Rahmen einer Beta gelöscht.

## English

Use the same checklist for the English release review. Stable readiness is
not established by documentation alone: every item needs PASS, BLOCKED, or NOT
RUN evidence. VMs are permanently monitoring-only, LXC simulation requires
explicit reviewed authorization, and real package installation remains
unsupported.

## Offene Stable-Entscheidungen / Open Stable decisions

- Stable needs a separately approved release and production rollout window.
- LXC helper/allowlist enablement remains a separate security decision.
- The Phase 31 joint activation plan is documented in
  `docs/phase31-lxc-activation-plan.md`; it is not an activation approval.
- VM package checks and simulations are permanently out of scope.
- A GitHub prerelease does not authorize installation in Home Assistant or on
  the Proxmox host.

## Beta.31 evidence status / Beta.31-Nachweisstatus

- [ ] Productive Beta.31 agent preflight and rollout: **NOT RUN**; separate
      authorization is required.
- [ ] Productive host or authorized-LXC simulation: **NOT RUN**; no helper or
      allowlist was enabled for this release.
- [x] Beta.31 mobile action-row contract and VM monitoring-only boundary are
      covered by the release CI browser and contract checks.
- [x] VM package checks and simulations remain permanently out of scope.
