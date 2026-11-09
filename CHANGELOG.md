# Changelog

## 0.1.0-beta.47 – Eligibility metadata recovery

### Deutsch

- Übernimmt nach einer gespeicherten Freigabe die nachgewiesenen Debian-/Ubuntu-
  und APT-Metadaten in den Update-Zieltyp, damit geeignete Container nicht mehr
  fälschlich als „Nicht unterstützt“ erscheinen.
- Bewahrt die sichere Trennung zwischen gespeicherter Autorisierung und
  tatsächlicher Eligibility; `discover_only` führt weiterhin keine Gastprobe aus.
- Die Lovelace-Karte validiert Serviceantworten auch bei HTTP 200 mit eingebettetem
  Fehler und zeigt Fehler statt einer irreführenden Erfolgsmeldung an.
- Beta.45-Inventar-Recovery und Beta.46-Berechtigungsfeedback bleiben enthalten.

### English

- After a stored grant, proven Debian/Ubuntu and APT metadata is carried into the
  update target so eligible containers are no longer shown as unsupported.
- The safe separation between stored authorization and actual eligibility remains;
  `discover_only` still performs no guest probe.
- The Lovelace card validates service responses even when HTTP 200 contains an
  embedded error and shows the error instead of misleading success feedback.
- Beta.45 inventory recovery and Beta.46 permission feedback remain included.

## 0.1.0-beta.46 – Permission feedback and inventory recovery

### Deutsch

- LXC-Berechtigungsbuttons zeigen laufende, erfolgreiche und fehlgeschlagene
  Serviceaufrufe direkt in der Karte an.
- HTTP-Fehler (400/403/500) und Timeouts werden nicht mehr nur im `title`-Attribut
  versteckt; der Ladezustand wird immer zurückgesetzt.
- Erfolgreiche `set_permissions`-Aufrufe lösen einen Coordinator-Refresh aus, damit
  Entity-Registry und Update-Status zeitnah zurückgelesen werden.
- Sicherheitsgrenzen bleiben unverändert: keine automatische Freigabe, keine
  Änderungen an `execution_enabled`, Allowlist oder produktiven HA-Systemen.

### English

- LXC permission buttons now show in-progress, successful, and failed service calls
  directly in the card.
- HTTP 400/403/500 errors and timeouts are no longer hidden only in the `title`
  attribute; loading state is always reset.
- Successful `set_permissions` calls request a coordinator refresh so entity state
  and update status are read back promptly.
- Security boundaries remain unchanged: no automatic grant and no changes to
  `execution_enabled`, allowlists, or productive Home Assistant systems.

## 0.1.0-beta.45 – inventory recovery candidate

### Deutsch

- Behebt die fehlende dynamische Erzeugung von VM- und LXC-Entitäten nach
  einem fehlgeschlagenen ersten Coordinator-Poll.
- Prüft den Recovery-Ablauf mit 2 VMs und 10 LXCs, deduplizierte Folge-Polls,
  Entity-Registry sowie Unload/Reload-Lifecycle.
- Ergänzt die Browser-Vertragsprüfung für die Anzeige von 2 VMs und 10 LXCs.
- Enthält nur einen Vorschlag für kompaktere mobile Host-Kennzahlen; eine
  größere UI-Umgestaltung ist nicht Bestandteil dieses Bugfixes.

### English

- Fixes missing dynamic VM and LXC entity creation after a failed first
  coordinator poll.
- Covers recovery with 2 VMs and 10 LXCs, duplicate-free follow-up polls, the
  entity registry, and unload/reload lifecycle behavior.
- Adds a browser contract check for rendering 2 VMs and 10 LXCs.
- Includes only a proposal for more compact mobile host metrics; no larger UI
  redesign is part of this bug fix.

This is an unreleased candidate. Merge, publication and productive installation
require separate approval.

## 0.1.0-beta.44 – Policy-Transport-Hotfix-Kandidat

### Deutsch

- Behebt den Beta.43-HTTP-500-Fehler bei `GET /api/v1/orchestration` unter
  `root:root 0700`-Policy-Verzeichnissen.
- Der unprivilegierte Agent greift nicht mehr direkt auf die Allowlist-Datei
  zu; Lesen und Schreiben laufen ausschließlich über den authentifizierten
  root-owned Helper-Socket.
- Der Orchestrierungsstatus prüft die Policy-Verfügbarkeit pro Anfrage über
  den Helper und meldet bei Helper-Ausfall sicher `policy_unavailable`.
- `ProtectSystem=strict`, `root:root 0600`, getrennte Berechtigungen und
  `execution_enabled=false` bleiben unverändert.

### English

- Fixes the Beta.43 HTTP 500 from `GET /api/v1/orchestration` with
  `root:root 0700` policy directories.
- The unprivileged agent no longer accesses the allowlist file directly;
  reads and writes use only the authenticated root-owned helper socket.
- Orchestration status checks policy availability per request through the
  helper and reports `policy_unavailable` safely when the helper is unavailable.
- `ProtectSystem=strict`, `root:root 0600`, separate permissions and
  `execution_enabled=false` remain unchanged.

This is a release candidate only. Merge, publication and productive
installation require separate approval.

## 0.1.0-beta.43 – systemd-Policy-Write-Fix-Kandidat

### Deutsch

- Behebt den nachgewiesenen Beta.42-Fehler beim ersten atomaren Policy-Write:
  Die systemd-Unit gibt ausschließlich das root-owned Policy-Verzeichnis frei;
  `ProtectSystem=strict` bleibt aktiv.
- Der Helper prüft Verzeichnis, Symlinks, Besitzer, Modi und Daten vor dem
  Schreiben, verwendet eine temporäre Datei auf demselben Dateisystem,
  synchronisiert Datei und Verzeichnis und räumt Fehlerdateien auf.
- Der Installer erhält bestehende Grants, setzt das Policy-Verzeichnis auf
  root-owned `0700` und dokumentiert die Migration sowie den Rollbackpfad.
- Der Orchestrierungsstatus wird pro API-Abfrage neu gelesen, damit ein
  Startreihenfolge-/Caching-Rennen den HA-Status nicht dauerhaft auf
  `unavailable` festhält.

### English

- Fixes the proven Beta.42 first atomic policy-write failure: the systemd unit
  grants write access only to the root-owned policy directory and keeps
  `ProtectSystem=strict` enabled.
- The helper validates directory, symlink, ownership, mode and data safety,
  uses a same-filesystem temporary file, synchronizes file and directory, and
  removes temporary files on failure.
- The installer preserves existing grants, enforces a root-owned `0700` policy
  directory, and documents migration and rollback.
- Orchestration status is read for each API request so startup ordering or
  caching cannot leave the HA status stuck at `unavailable`.

This is a release candidate only. Merge, publication, productive installation,
grants, package actions and restarts require separate approval.

## 0.1.0-beta.42 – Read-only Grant-Eignungsprüfung

### Deutsch

- Behebt den Grant-Deadlock für noch nicht autorisierte LXCs mit unbekanntem
  Discovery-OS: Der Agent fordert vor einer Simulationsfreigabe eine strikt
  read-only Prüfung über den authentifizierten root-Helper an.
- Die Prüfung bestätigt laufenden LXC-Status, Debian/Ubuntu aus
  `/etc/os-release` und die festen APT-Binaries; sie führt kein `apt` oder
  `apt-get` aus und bleibt bei Unsicherheit fail-closed.
- Widerruf funktioniert unabhängig von einer erneuten Eignungsprüfung und
  erhält die bestehende Metadatenbasis. Simulations- und Update-Rechte bleiben
  getrennt.
- Die HA-Anzeige übernimmt sichere, verständliche Ablehnungsgründe statt der
  pauschalen Meldung „agent returned an HTTP error“.

### English

- Fixes the first-grant deadlock for unauthorized LXCs with unknown discovery
  OS data by performing a strictly read-only eligibility probe through the
  authenticated root helper.
- The probe verifies a running LXC, Debian/Ubuntu from `/etc/os-release`, and
  fixed APT binaries; it runs no `apt` or `apt-get` command and fails closed on
  uncertainty.
- Revocation works without a fresh eligibility probe and preserves existing
  metadata. Simulation and update rights remain separate.
- HA now surfaces safe, understandable rejection reasons instead of the
  generic “agent returned an HTTP error” message.


## 0.1.0-beta.41 – Beta.40-Policy-Migrationsfix-Kandidat

### Deutsch

- Behebt die Migration bestehender `root:root 0600`-Policies: Der Agent liest
  und schreibt die Policy nicht mehr direkt, sondern ausschließlich über den
  authentifizierten root-eigenen Helper-Socket.
- Der Helper akzeptiert nur die festen Operationen `policy_read` und
  `policy_set`, prüft den Agent-Peer per `SO_PEERCRED` und schreibt atomar
  weiterhin root-owned mit Modus `0600`.
- Fehlende, beschädigte oder unberechtigte Policies bleiben fail-closed;
  `execution_enabled=false` und die getrennte Simulation-/Update-Freigabe
  ändern sich nicht.
- Beta.41 ist veröffentlicht; der echte Proxmox-LXC-Paketlauf bleibt offen.

### English

- Fixes migration of existing `root:root 0600` policies: the agent no longer
  reads or writes the policy file directly and uses only the authenticated
  root-owned helper socket.
- The helper accepts only fixed `policy_read` and `policy_set` operations,
  verifies the agent peer with `SO_PEERCRED`, and atomically preserves
  root-owned mode `0600`.
- Missing, damaged or unauthorized policies remain fail-closed;
  `execution_enabled=false` and separate simulation/update authorization are
  unchanged.
- Beta.41 is published; the real Proxmox LXC package run remains open.

## 0.1.0-beta.40 – Release-Kandidat für die kontrollierte Migration

### Deutsch

- Synchronisiert Agent, Home-Assistant-Integration und Lovelace-Karte auf die
  eindeutige Kandidatenversion Beta.40; Beta.39 bleibt unverändert.
- Bereitet die Migration von HA Beta.39/Agent Beta.37 auf den geprüften PR-65-
  Stand vor, ohne produktive Berechtigungen, Paketaktionen oder Neustarts.
- Der echte `helper → pct → nichtproduktiver LXC`-Nachweis bleibt offen; dieser
  Kandidat ist nicht als vollständige E2E-Abnahme oder Stable freigegeben.

### English

- Synchronizes the agent, Home Assistant integration and Lovelace card on the
  unique Beta.40 candidate version; Beta.39 remains unchanged.
- Prepares migration from HA Beta.39/Agent Beta.37 to the reviewed PR-65 state
  without productive permission changes, package actions or restarts.
- The real `helper → pct → non-production LXC` proof remains open; this
  candidate is not fully E2E-accepted and is not Stable.

## Unreleased – Issue #63 E2E-Abschluss offen

### Deutsch

- Die Dokumentation stellt klar, dass Beta.39 keine vollständige LXC-E2E-Abnahme ist.
- PR #65 ergänzt einen festen Helper-Transporttest bis zu einem Wegwerf-Gastroot
  mit echter dpkg-Installation und Upgrade; der Test ist ausdrücklich kein
  Ersatz für einen echten Proxmox-LXC.
- Read-only auf `pve-home` wurde bestätigt: alle vorhandenen LXCs sind
  produktive Dienste, CT112 bleibt gestoppt, und es gibt keinen ausgewiesenen
  Testgast. Es wurden keine produktiven Paketaktionen ausgeführt.
- Kein Merge, kein Release und kein Issue-Abschluss, solange der echte
  `pct`-Transport mit einem nichtproduktiven LXC nicht nachgewiesen ist.

### English

- Documentation clarifies that Beta.39 is not complete LXC E2E acceptance.
- PR #65 adds a fixed helper transport test to a disposable guest root with a
  real dpkg install and upgrade; it is explicitly not a real Proxmox LXC test.
- Read-only inspection of `pve-home` confirmed that all existing LXCs are
  productive services, CT112 remains stopped, and no designated test guest
  exists. No productive package action was executed.
- No merge, release, or issue closure is allowed until the real `pct` transport
  is proven with a non-production LXC.

## 0.1.0-beta.39 – LXC-Updateberechtigungen und isolierte E2E-Abnahme

### Deutsch

- Simulation und echte Updates werden pro laufendem LXC über den geschützten Agent-Endpunkt getrennt autorisiert.
- Frische, autorisierte Simulationen sind auch bei null verfügbaren Updates über die Karte möglich.
- CI weist eine echte Paketinstallation und ein Upgrade in einem ephemeren dpkg-Testroot nach.
- VMs, Host, gestoppte oder nicht nachgewiesene Gäste bleiben ausgeschlossen; `execution_enabled` bleibt die Ausführungsgrenze.

### English

- Simulation and real updates are authorized separately per running LXC through the protected agent endpoint.
- Fresh authorized simulations remain available when zero updates are present.
- CI proves a real package installation and upgrade in an ephemeral dpkg test root.
- VMs, the host, stopped or unproven guests remain excluded; `execution_enabled` remains the execution gate.

## 0.1.0-beta.38 – API-kompatible Agent-Weiterentwicklung

### Deutsch

- Bewertet neuere Beta-Agenten mit demselben API-Vertrag 1.1 als kompatibel.
- Beta-Agenten derselben 0.1.0-Release-Linie mit API-Vertrag 1.1 bleiben kompatibel; abweichende API-Verträge und unbekannte Versionen bleiben fail-closed.
- Die Update- und Simulationsberechtigungen werden dadurch nicht erweitert.

### English

- Treats newer beta agents with the same API contract 1.1 as compatible.
- Older agents, mismatched API contracts and unknown versions remain fail-closed.
- This change does not expand update or simulation permissions.

## 0.1.0-beta.37 – LXC-Namespace-Ausführung

### Deutsch

- Erlaubt dem root-eigenen, streng begrenzten Helper den notwendigen Namespace-Aufbau für unprivilegierte LXCs.
- Alle festen Operationen, Zeitlimits, Socket-/Peer-UID- und Allowlist-Grenzen bleiben erhalten.
- Keine Paketaktion wird automatisch aktiviert; `execution_enabled` bleibt deaktiviert.

### English

- Allows the root-owned, tightly scoped helper to perform the namespace setup required by unprivileged LXCs.
- Fixed operations, timeouts, socket/peer-UID and allowlist boundaries remain enforced.
- No package action is enabled automatically; `execution_enabled` remains disabled.

## 0.1.0-beta.36 – Proxmox-ACL-kompatibler LXC-Helper
## 0.1.0-beta.36 – Proxmox-ACL-kompatibler LXC-Helper

### Deutsch

- Helper und Discovery laufen wieder mit primärer root-Gruppe, damit Proxmox-IPC-Zugriff erhalten bleibt.
- Runtime-Verzeichnis und Unix-Sockets werden weiterhin ausschließlich für die Agent-Gruppe freigegeben.
- Keine Erweiterung der Allowlist; `execution_enabled` bleibt standardmäßig deaktiviert.

### English

- Helper and discovery retain a root primary group so Proxmox IPC access continues to work.
- The runtime directory and Unix sockets remain accessible only to the agent group.
- No allowlist expansion; `execution_enabled` remains disabled by default.

## 0.1.0-beta.35 – LXC-Helper-Authentifizierung und Runtime-Berechtigungen

### Deutsch

- Korrigiert die `SO_PEERCRED`-Auswertung des root-eigenen Helpers, damit der
  Agent anhand der tatsächlichen Peer-UID autorisiert wird.
- Stellt die gemeinsame systemd-Runtime-Gruppe für Discovery-Socket und
  Helper-Socket sicher.

### English

- Corrects `SO_PEERCRED` parsing so the root-owned helper authorizes the actual
  agent peer UID.
- Aligns the shared systemd runtime group for discovery and helper sockets.

Die Updateausführung bleibt opt-in und standardmäßig deaktiviert. / Update
execution remains opt-in and disabled by default.

## 0.1.0-beta.34 – kontrollierte LXC-Updateausführung

### Deutsch

- getrennte Berechtigungen für Simulation und echte Updates;
- plan-gebundenes `apt-get update` plus `apt-get --yes --no-remove upgrade` für
  ausdrücklich autorisierte laufende Debian-/Ubuntu-LXCs;
- fester Helper mit Timeout, exklusiver Ausführung, Phasenstatus und ohne
  Dist-Upgrade, Entfernung, VM-/Host-Zugriff oder automatische Neustarts;
- HA-Service und Kartenbutton bleiben bei fehlender Berechtigung deaktiviert.

### English

- separate simulation and real-update permissions;
- plan-bound `apt-get update` plus `apt-get --yes --no-remove upgrade` for
  explicitly authorized running Debian/Ubuntu LXCs;
- fixed helper with timeout, exclusive execution, phase results, and no
  dist-upgrade, removal, VM/host access, or automatic reboot;
- the HA service and card button remain disabled without authorization.

## 0.1.0-beta.33 – Release-Konsistenz und sichere Updategrenzen (Prerelease)

### Deutsch

- Synchronisiert Manifest, Agent-Version, HA-Integration und Karten-Cache auf
  denselben Beta.33-Releasezustand.
- Ergänzt eine Regression gegen auseinanderlaufende Versionsangaben.
- Bestätigt den unveränderten Sicherheitsvertrag: gezielte APT-Simulationen
  bleiben möglich, echte Installationen, Entfernungen und `apt update` bleiben
  deaktiviert.

### English

- Synchronizes the manifest, agent version, Home Assistant integration, and
  card cache to the same Beta.33 release state.
- Adds a regression guard against diverging version declarations.
- Confirms the unchanged safety contract: targeted APT simulations remain
  available, while real installs, removals, and `apt update` remain disabled.

## 0.1.0-beta.32 – sichere Orchestrierungsanzeige (Prerelease)

### Deutsch

- Ergänzt den read-only Orchestrierungsstatus für Helper, Discovery-Socket,
  Integrität und `discover_only` in der Agent-API.
- Home Assistant fragt den optionalen Status rückwärtskompatibel ab und zeigt
  einen Helper-Status als `ready`, `not_installed` oder `unavailable`.
- Die Integration aktiviert keine Helper-, Socket-, Allowlist- oder
  Gastzugriffsrechte automatisch; echte Paketaktionen bleiben deaktiviert.

### English

- Adds the read-only orchestration status for helper, discovery socket,
  integrity, and `discover_only` to the agent API.
- Home Assistant polls the optional status backward-compatibly and exposes a
  helper status of `ready`, `not_installed`, or `unavailable`.
- The integration never activates helper, socket, allowlist, or guest access
  automatically; real package actions remain disabled.

## Unreleased – weitere Entwicklung

### Deutsch

- Ergänzt die isolierte Phase-35-Orchestrierung mit versionierter,
  fail-closed Policy (`discover_only` als Standard und ausdrücklich wählbares
  `auto_eligible`), fester Discovery-Probe und deterministischem Allowlist-Plan.
- Neue, gestoppte, entfernte, unbekannte oder veraltete Ziele erzeugen keine
  neue Berechtigung; VMs und ungültige IDs bleiben ausgeschlossen. Die Policy
  wird atomar und mit sicheren Dateirechten gespeichert.
- Ergänzt Phase 36 als isolierte automatische Einrichtung: peer-authentifizierter
  Discovery-Socket, serialisierter expliziter Allowlist-Apply-Controller,
  maschinenlesbarer Orchestrierungsstatus und HA-Auswahl des Policy-Modus.
  Produktive Aktivierung bleibt separat freigabepflichtig.
- Ergänzt Phase 37 als isolierte End-to-End-Abnahme für Inventar, Probe, Policy,
  Plan, expliziten Apply, Audit, Recovery und Status; Proxmox, systemd, HA und
  produktive Gäste bleiben unberührt.
- Ergänzt Phase 39 als separaten Root-/systemd-Installer-Test auf einem
  kurzlebigen GitHub-Runner; Apply, Wiederholung, Socket-Health, Rechte und
  fail-closed Quellintegrität werden geprüft, ohne pve-home zu verändern.
- Ergänzt Phase 41 um einen JSON-Preflight mit eindeutiger GO/NO-GO-Entscheidung
  sowie den read-only Prüf-, Upgrade- und Rückfallvertrag für Beta.31.
- Ergänzt Phase 45 um eine read-only Orchestrierungs-Statusverdrahtung für
  Helper, Discovery-Socket, Integrität und `discover_only`; der Status wird in
  API und Home Assistant angezeigt, ohne produktive Aktivierung.

- Präzisiert den Backend-Status für einen fehlenden oder ungültigen LXC-Helper
  als `helper-unavailable`, getrennt von `unauthorized`, `unsupported` und
  `not_checked`.
- Ergänzt verständliche deutsche und englische Dashboard-Meldungen sowie eine
  nicht autorisierende Allowlist-Vorlage.
- Helper, Allowlist und Produktivpfade bleiben deaktiviert; keine Gastbefehle
  oder Simulationen wurden ausgeführt.
- Ergänzt die passive Phase-29-Matrix für alle zehn LXCs mit Ressourcen,
  Proxmox-OS-Metadaten, unbekannten APT-Nachweisen, Betriebsrisiken und den
  späteren Einzel-Freigabegates.
- Ergänzt die Phase-30-Nachweise: CT101–109 Debian 13 mit apt 3.0.4 und
  CT110–111 Debian 12 mit apt 2.6.2; die geplante Allowlist bleibt inaktiv.
- Ergänzt den Phase-31-Gesamtplan für alle neun laufenden LXCs mit
  Einzelabnahme, Negativtests, Abbruchkonzept und gemeinsamer Sicherheitsgrenze;
  produktive Aktivierung bleibt separat freigabepflichtig.

### English

- Adds the isolated Phase 35 orchestration layer with a versioned fail-closed
  policy (`discover_only` by default and explicitly selectable
  `auto_eligible`), a fixed discovery probe, and a deterministic allowlist plan.
- New, stopped, removed, unknown, or stale targets never create new access;
  VMs and invalid IDs remain excluded. Policy persistence is atomic and uses
  secure file permissions.
- Adds the isolated Phase 36 setup/orchestration layer: peer-authenticated
  discovery socket, serialized explicit allowlist apply controller,
  machine-readable orchestration status, and an HA policy-mode selector.
  Production activation still requires separate approval.
- Adds the isolated Phase 37 end-to-end acceptance harness for inventory,
  probe, policy, plan, explicit apply, audit, recovery, and status; Proxmox,
  systemd, HA, and production guests remain untouched.

- Reports a missing or invalid LXC helper as `helper-unavailable`, distinct
  from `unauthorized`, `unsupported`, and `not_checked`.
- Adds clear German and English dashboard messages and a non-authorizing
  allowlist template.
- The helper, allowlist, and production execution paths remain disabled; no
  guest command or simulation was run.
- Adds the passive Phase 29 matrix for all ten LXCs, including resources,
  Proxmox OS metadata, unknown APT evidence, operating risks, and later
  per-target authorization gates.
- Adds the Phase 30 evidence: CT101–109 are Debian 13 with apt 3.0.4 and
  CT110–111 are Debian 12 with apt 2.6.2; the planned allowlist remains
  inactive.
- Adds the Phase 31 joint plan for all nine running LXCs with per-target
  acceptance, negative tests, abort handling, and a shared security boundary;
  production activation still requires separate approval.
- Adds Phase 45 read-only orchestration status wiring for helper, discovery
  socket, integrity, and `discover_only`; API and Home Assistant expose the
  status without activating production components.

## 0.1.0-beta.31 – Mobile Aktionszeile und Simulationsgrenzen (Prerelease)

### Deutsch

- Trennt Aktionszeile und Simulationsergebnis: beide Schaltflächen behalten
  gleiche, touch-taugliche Abmessungen; Ergebnis, Paketanzahl,
  Sicherheitsstatus und Details erscheinen darunter.
- Prüft die stabile Geometrie, Paketdetail-Interaktion, lange Versionen,
  Dark Mode, iPhone/iPad/Desktop-Ansichten und Scrollstabilität im Browser-
  Harness.
- Dokumentiert die read-only Eignungsmatrix für alle zehn LXCs. Der optionale
  Helper bleibt deaktiviert; keine produktive Allowlist wird verändert.
- Dokumentiert VM 104 (HAOS) und VM 106 (PBS) dauerhaft als Monitoring-only.
  Keine VM-Paketprüfung, Simulation, `pct exec`-Weiterleitung oder echte
  Installation wird hinzugefügt.

### English

- Separates the action row from simulation results so both buttons keep equal,
  touch-friendly dimensions while results, package counts, safety, and details
  render below.
- Covers stable geometry, package details, long versions, dark mode,
  iPhone/iPad/desktop viewports, and scroll stability in the browser harness.
- Documents the read-only readiness matrix for all ten LXCs; the optional
  helper remains disabled and no production allowlist is changed.
- Documents VM 104 (HAOS) and VM 106 (PBS) as permanently monitoring-only.
  No VM package check, simulation, `pct exec` forwarding, or real install is
  added.

## 0.1.0-beta.30 – Mobile UI und dauerhafter VM-Ausschluss (Prerelease)

### Deutsch

- Kompakte, mobile Simulationskarten mit sichtbarer Paketanzahl,
  Sicherheitsstatus und standardmäßig eingeklappten Paketdetails.
- Paketname sowie installierte und verfügbare Version werden sicher und ohne
  HTML-Injection dargestellt; lange Versionen umbrechen und die Scrollposition
  bleibt stabil.
- LXC-Eignung bleibt an laufenden Zustand, Debian/Ubuntu-APT-Nachweis und
  explizite Zielautorisierung gebunden. VMs sind dauerhaft von Paketprüfung
  und Simulation ausgeschlossen; ihre Karten zeigen weiterhin Name, Status und
  Ressourcen sowie einen Hinweis auf die Updatefunktion des Gastbetriebssystems.
- Gleichzeitige Simulationen desselben Ziels werden abgewiesen;
  Installationspfade bleiben deaktiviert.

### English

- Compact mobile simulation cards show package counts, safety status, and
  collapsed package details by default.
- Package names and installed/available versions are rendered safely without
  HTML injection; long versions wrap and scroll position remains stable.
- LXC eligibility remains bound to running state, proven Debian/Ubuntu APT,
  and explicit target authorization. VMs are permanently excluded from
  package checks and simulations; their cards still show name, state, and
  resources and direct users to the guest operating system's update function.
- Concurrent simulations for one target are rejected; installation paths
  remain disabled.

## 0.1.0-beta.29 – Sichere systemd-Lebenszyklusprüfung (Prerelease)

### Deutsch

- Bindet die Restart-Prüfung an `InvocationID` und
  `ExecMainStartTimestampMonotonic`.
- Behandelt fehlende, ungültige, gestiegene und unerwartet zurückgesetzte
  `NRestarts`-Werte sicher und lässt nur den erwarteten kontrollierten
  alten→neuen Unit-Wechsel zu.
- Führt bei einem nicht eindeutigen Lebenszyklus sicher den bestehenden
  Rollback aus.
- Enthält weiterhin den Beta.28-APT-Parser-Fix für `amd64` und `all`.

### English

- Binds restart validation to `InvocationID` and
  `ExecMainStartTimestampMonotonic`.
- Fails safely on missing, invalid, increased, or unexpected reset
  `NRestarts` values and allows only the expected controlled old-to-new unit
  transition.
- Uses the existing safe rollback when the lifecycle is ambiguous.
- Continues to include the Beta.28 APT parser fix for `amd64` and `all`.

## 0.1.0-beta.28 – APT-Parser und stale-Status-Lebenszyklus (Prerelease)

### Deutsch

- Behält beim Parsen von `apt list --upgradable` die installierte Version
  auch dann bei, wenn die reguläre Architekturspalte (`amd64`, `all`) vor
  der Upgradable-Markierung steht. Dadurch werden identische Host-Pläne nicht
  mehr fälschlich als stale abgebrochen; echte Paket- oder
  Versionsabweichungen bleiben blockiert.

### English

- Preserves the installed version when parsing `apt list --upgradable` with
  its regular architecture column (`amd64`, `all`) before the upgradable
  marker. Identical host plans are no longer falsely rejected as stale; real
  package or version changes remain blocked.

### Lebenszyklus / Lifecycle

### Deutsch

- Der HA-Coordinator hält das letzte Dry-Run-Ergebnis getrennt von aktuellen
  Update-Metadaten im Arbeitsspeicher. Ein alter stale-Status wird nicht
  automatisch gelöscht oder zurückgesetzt; eine neue Dry-Run-Antwort muss den
  Ergebnisstand ausdrücklich ersetzen.

### English

- The HA coordinator keeps the last dry-run result separate from current update
  metadata in memory. An old stale status is not automatically deleted or
  reset; a new dry-run response must explicitly replace the result state.

## 0.1.0-beta.24 – Kanonischer Dry-Run-Planvergleich (Prerelease)

### Deutsch

- Normalisiert Paketpläne vor dem Digest-Vergleich; reine Reihenfolgeänderungen
  zwischen APT-Cache und Simulation lösen keinen falschen Stale-Abbruch mehr aus.
- Behält den sicheren Abbruch bei echten Planänderungen unverändert bei.
- Zeigt unbekannte Speicherwerte nicht mehr als 0 % und übersetzt fehlenden
  Gastzugriff verständlich.
- Stabilisiert das responsive Aktionslayout ohne Installationspfad.

### English

- Canonicalizes package plans before digest comparison so source ordering alone
  no longer causes a false stale-plan rejection.
- Keeps the safety abort for real plan changes unchanged.
- Does not render unknown memory values as 0% and localizes missing guest access.
- Stabilizes the responsive action layout without adding an installation path.

## 0.1.0-beta.23 – Dry-Run-Serviceauswahl (Kandidat)

### Deutsch

- Behebt den Fehler, bei dem `dry_run` ohne `entry_id` ein internes
  Setup-Flag als Coordinator verwendete und dadurch mit
  `bool has no attribute transport` abbrach.
- Ergänzt Regressionen für erfolgreiche Antworten, HTTP-/TLS-Fehler,
  Zeitüberschreitungen und ungültige Ziele.
- Zeigt die Simulationsaktion für Host, VMs und LXCs immer an; nicht
  autorisierte oder nicht unterstützte Ziele bleiben sichtbar und deaktiviert.
- Zeigt die dauerhaft deaktivierte Installationsaktion einheitlich und
  responsiv neben beziehungsweise unter der Simulation an und übersetzt
  Autorisierungsfehler ins Deutsche.
- Der Service bleibt `SupportsResponse.ONLY`; echte Updates bleiben
  serverseitig deaktiviert.

### English

- Fixes `dry_run` without `entry_id` selecting an internal setup flag as the
  coordinator, which caused `bool has no attribute transport`.
- Adds regressions for successful responses, HTTP/TLS errors, timeouts, and
  invalid targets.
- Keeps the simulation action visible for hosts, VMs, and LXCs while disabling
  unauthorized or unsupported targets with a clear reason.
- Keeps the permanently disabled install action in a consistent responsive
  layout and localizes authorization errors in German.
- The service remains `SupportsResponse.ONLY`; real updates remain disabled
  server-side.

## 0.1.0-beta.22 – sicherer Agent-Preflight (Prerelease)

### Deutsch

- Erkennt eindeutig historische Rollback-Staging-Stände und lässt sie
  unverändert bestehen.
- Blockiert weiterhin aktive, ungültige oder mehrdeutige Upgrade-Zustände.
- Wählt den Rollback-Stand beim Austausch anhand der zuvor aktiven Version
  statt anhand einer zufälligen Verzeichnisreihenfolge.
- Keine produktive Agent-, HA- oder LXC-Änderung durch dieses Release.

### English

- Recognizes provably historical rollback staging and preserves it unchanged.
- Continues to block active, invalid, or ambiguous upgrade states.
- Selects the rollback state by the previously active version instead of an
  arbitrary directory order during an update.
- This release makes no productive agent, HA, or LXC changes.

## 0.1.0-beta.21 – sicherer LXC-Gastzugriff (Prerelease)

### Deutsch

- Root-seitiger Helper für strikt allowlistete, passive LXC-APT-Lese-
  und Dry-Run-Operationen dokumentiert und mit Sicherheitsregressionen
  abgesichert.
- Socket-Clients werden per `SO_PEERCRED` auf die exakte Agent-UID begrenzt;
  Allowlist, Request, Prozesslaufzeit und Ausgabe werden pro Anfrage begrenzt
  und geprüft.
- Keine produktive Installation, sudoers-Änderung oder Allowlist-Aktivierung;
  echte Updateausführung bleibt deaktiviert.

### English

- Added a root-side helper candidate for tightly allowlisted, passive LXC APT
  reads and simulations, with security regression coverage.
- Unix-socket clients are restricted to the exact agent UID via `SO_PEERCRED`;
  allowlist, requests, process lifetime, and output are bounded per request.
- No production installation, sudoers change, or allowlist activation; real
  update execution remains disabled.

## Unreleased – Agent-Updater Readiness und Rollback

### Deutsch

- Der Agent-Updater wartet nach dem Dienststart innerhalb eines begrenzten
  Zeitfensters auf einen TLS-validierten Healthcheck mit passender Version und
  API 1.1.
- Fehlerpfade verwenden einen EXIT-sicheren Rollback; der fehlerhafte Code
  bleibt zur Diagnose erhalten und vorhandenes Rollback-Staging wird nicht
  automatisch gelöscht.

### English

- The agent updater now waits within a bounded window for a TLS-validated
  health response with the expected version and API 1.1.
- Failure paths use EXIT-safe rollback; failed code remains available for
  diagnosis and existing rollback staging is never deleted automatically.

## 0.1.0-beta.19 – Dry-Run-Serviceantwort und Update-Erkennung (Prerelease)

### Deutsch

- Fordert die verpflichtende Home-Assistant-Serviceantwort für
  `smart_homelab_maintenance.dry_run` korrekt an.
- Zeigt Simulationsergebnis, Paketänderungen, Warnungen, Sicherheitsbewertung,
  leere Antworten, Servicefehler und Zeitüberschreitungen in der Karte an.
- Keine echten Updates, keine automatische Freigabe und keine produktiven
  Änderungen.
- Bewahrt eindeutige Zustände der passiven Update-Erkennung und macht
  `unsupported`, `not_checked`, `unauthorized`, `error`, `stale` und `unknown`
  in API und Karte sichtbar.
- Erlaubt spätere Gast-Allowlist-Metadaten nur für feste Ziel-IDs, OS-/Versions-
  und Paketmanagerangaben; Befehle, Pfade und Credentials bleiben ausgeschlossen.

### English

- Correctly requests the mandatory Home Assistant service response for
  `smart_homelab_maintenance.dry_run`.
- Displays simulation results, package changes, warnings, safety assessment,
  empty responses, service errors, and timeouts in the card.
- No real updates, automatic approval, or productive changes are enabled.
- Preserves explicit passive update states and displays `unsupported`,
  `not_checked`, `unauthorized`, `error`, `stale`, and `unknown` in the API and
  card.
- Future guest allowlist metadata is limited to fixed target IDs, OS/version,
  and package-manager fields; commands, paths, and credentials are excluded.

Beta.19 is published as a GitHub prerelease. HACS updates the Home Assistant
integration and card only; the separately running agent requires its own
reviewed, explicitly approved update process. No productive agent or guest
system was changed by this release.

## 0.1.0-beta.18 – gemeinsamer Versions- und Updatevertrag

- DE: Integration, Lovelace-Karte und Agent melden eine gemeinsame Version und
  einen expliziten API-Vertrag. Abweichungen werden als aktuell, veraltet,
  inkompatibel oder unbekannt angezeigt. Der Agent-Updateprozess ist
  ausdrücklich bestätigt, transaktional und nach dem Healthcheck rückrollbar;
  echte Systemupdates bleiben deaktiviert.
- EN: Integration, Lovelace card, and agent expose one coordinated version plus
  an explicit API contract. Mismatches are shown as current, outdated,
  incompatible, or unknown. Agent updates require explicit confirmation, use a
  transactional health-checked path, and can roll back; real system updates
  remain disabled.

## 0.1.0-beta.17 – Ressourcen- und Agent-Vertrag (Prerelease)

### Deutsch

- Ergänzt `agent_version` im öffentlichen Healthcheck, damit HA-Integration
  und separat laufender Wartungsagent auf denselben Beta-Stand geprüft werden
  können.
- Korrigiert die Proxmox-Projektion: fehlende CPU-/RAM-/Speicherwerte bleiben
  unbekannt statt als `0` zu erscheinen; erfolgreiche API-Erreichbarkeit wird
  nicht wegen fehlender optionaler Messwerte als Host-offline bewertet.
- Bewahrt die funktionierenden LXC-Freiwerte und trennt sie von VM-Werten,
  für die Proxmox keine Gast-Dateisystem- oder Gast-RAM-Freimessung liefert.
- Verdichtet die Karte mit beschrifteten CPU-, RAM- und Speicherbalken. Freie
  RAM-/Speicherwerte stehen direkt am jeweiligen Balken; fehlende Daten blenden
  den Balken aus.
- Keine echte Updateausführung, keine Paketinstallation und kein produktiver
  Zugriff. Beta.17 bleibt read-only; ein echter iPhone-Praxistest bleibt
  erforderlich.
- Für die neuen Ressourcenwerte müssen Integration und separat laufender Agent
  gemeinsam auf Beta.17 stehen; ein reines HACS-Update aktualisiert den Agenten
  nicht.

### English

- Adds `agent_version` to the public health response so the HA integration and
  separately running maintenance agent can be checked for the same beta line.
- Fixes Proxmox projection: missing CPU, RAM, and storage values remain
  unknown instead of becoming fabricated zeroes; successful API reachability
  is not reported as host offline because optional metrics are absent.
- Preserves working LXC free-resource values and separates them from VM
  values when Proxmox does not provide guest filesystem or guest-RAM free data.
- Makes the card more compact with labelled CPU, RAM, and storage bars. Free
  RAM/storage values appear beside the relevant bar; missing data hides the bar.
- No real update execution, package installation, or productive access. Beta.17
  remains read-only; a real iPhone field test is still required.
- The integration and separately running agent must both be on Beta.17 for the
  new resource fields; a HACS update alone does not update the agent.

## 0.1.0-beta.16 – Fehlerisolierung für Update-Abfragen (Prerelease)

### Deutsch

- Behebt einen Beta.15-Fehler, bei dem ein HTTP-Fehler der optionalen
  `/api/v1/updates`-Abfrage Host-, VM- und LXC-Daten komplett ausblendete.
- Führt Update-Abfragen getrennt vom Kerninventar aus; bei einem Fehler bleiben
  die Bestandsdaten sichtbar und der Updatezustand wird als unbekannt gemeldet.
- Behebt den von Home Assistant 2026.11 gemeldeten thread-unsicheren Aufruf
  von `hass.async_create_task` im Intervall-Callback.
- Echte Updateausführung bleibt serverseitig deaktiviert; Dry Runs bleiben die
  einzige erlaubte Aktionsstufe.
- Der iPhone-Scrollfix ist weiterhin nicht durch einen echten iOS-Praxistest
  bestätigt.

### English

- Fixes a Beta.15 regression where an HTTP error from the optional
  `/api/v1/updates` request hid all host, VM, and LXC inventory data.
- Runs update polling separately from core inventory; when it fails, inventory
  remains visible and the update state is reported as unknown.
- Fixes the thread-unsafe `hass.async_create_task` call in the interval
  callback reported by Home Assistant 2026.11.
- Real update execution remains server-disabled; dry runs remain the only
  permitted action level.
- The iPhone scroll fix is still not confirmed by a real iOS field test.

## 0.1.0-beta.15 – Sichere Update-Prüfung und Simulation (Kandidat)

### Deutsch

- Ergänzt passive Update-Erkennung für den Proxmox-Host und autorisierte
  Debian-/Ubuntu-LXC-Ziele über einen festen, begrenzten APT-Prüfpfad.
- Zeigt `aktuell`, `Updates verfügbar`, `unbekannt`, `nicht unterstützt` und
  Fehler getrennt; fehlende Messwerte werden nicht erfunden.
- Ergänzt einen ausdrücklich bestätigten Dry Run mit
  `apt-get --simulate --no-remove upgrade`. Paketindex-Aktualisierung,
  Installation, Entfernung und Neustarts finden nicht statt.
- Die Ausführung echter Updates ist serverseitig deaktiviert; die spätere
  Freischaltung muss zusätzlich aktuellen Dry Run, unveränderten Plan,
  Konflikt-/Entfernungsprüfung und ausdrückliche Bestätigung erzwingen.
- Beta.15 ist ein Releasekandidat. Der iPhone-Scrollfix bleibt ohne echten
  iOS-Praxistest unbestätigt.

### English

- Adds passive update detection for the Proxmox host and authorized
  Debian/Ubuntu LXC targets through a fixed, bounded APT inspection path.
- Distinguishes up to date, updates available, unknown, unsupported, and error;
  missing measurements are never fabricated.
- Adds an explicitly confirmed dry run using
  `apt-get --simulate --no-remove upgrade`. It does not refresh indexes,
  install or remove packages, or restart services.
- Real update execution is server-disabled. Any later enablement must enforce
  a current dry run, unchanged plan, conflict/removal checks, and explicit
  confirmation server-side.
- Beta.15 is a release candidate. The iPhone scroll fix remains unverified
  without a real iOS field test.

## 0.1.0-beta.14 – Sections-Resize- und Ressourcen-Kandidat

### Deutsch

- Meldet Änderungen der tatsächlichen Kartenhöhe über `ResizeObserver` als
  `card-updated`, damit Home Assistants Sections-Wrapper nach dem Öffnen von
  Detailbereichen neu layouten können.
- Ergänzt eine Sections-Fixture, die einen veralteten Wrapper-Höhenwert und
  das abgeschnittene Kartenende reproduziert; CT112 muss im reparierten Pfad
  erreichbar bleiben.
- Reicht CPU-, RAM-, Speicher- und Laufzeitfelder des read-only Proxmox-
  Backends bis zu den HA-Entitätsattributen durch.
- Die iPhone-Praxisbehebung bleibt unbestätigt; diese Version ist nur ein
  Kandidat und wurde nicht veröffentlicht oder produktiv installiert.

### English

- Reports actual card-size changes through `ResizeObserver` as `card-updated`,
  allowing Home Assistant Sections wrappers to re-layout after details open.
- Adds a Sections fixture reproducing stale wrapper height and clipped card
  endings; CT112 must remain reachable in the fixed path.
- Preserves CPU, RAM, storage, and uptime fields from the read-only Proxmox
  backend through to Home Assistant entity attributes.
- The iPhone fix remains unverified; this is a candidate only and was neither
  published nor installed in production.

## 0.1.0-beta.13 – Next Generation Dashboard (Kandidat)

- Modernisiert die read-only Lovelace-Karte mit klarer Statusübersicht,
  responsiven Kartenbreiten und aufklappbaren VM-/LXC-Details.
- Entfernt die wirkungslose `min_rows`-Angabe neben `rows: "auto"`; die Karte
  meldet weiterhin volle Sections-Breite und folgt ausschließlich ihrem Inhalt.
- Bewahrt DOM-Identität, offene Details, Fokus und Scrollposition bei HA-Updates.
- Erweitert die Browser-Regressionen um 0, 1, 10, 20 und 50 Container sowie
  erreichbare Kartenenden in simulierten Sections-/Masonry-Layouts.
- Kein produktiver Home-Assistant-/Proxmox-Zugriff und keine Veröffentlichung.

## 0.1.0-beta.11 – Lovelace-Scrollstabilität (Prerelease-Kandidat)

- Verhindert unnötiges Entfernen und Wiedereinfügen bestehender VM-/LXC-Karten
  bei gewöhnlichen `hass`-Aktualisierungen.
- Ergänzt Regressionen für Scrollposition, DOM-Identität, Grid-Mutationen,
  Fokus, äußeren Kartenbaum und drei unabhängige Karteninstanzen.
- Vollständige Browser-Matrix für iPhone-, iPad- und Desktop-Viewports sowie
  Home-Assistant-Runtime- und HACS-Prüfungen bleiben erforderlich.
- Kein automatischer Home-Assistant-Neustart, keine Installation und keine
  Änderungen an Proxmox oder dem Agenten.

## 0.1.0-beta.9 – Mobile Kartenstabilität (Kandidat)

- Bewahrt den geöffneten Proxmox-Hostbereich über mehrere Home-Assistant-
  Statusupdates hinweg.
- Ermittelt das responsive Kartenraster anhand der tatsächlichen Kartenbreite:
  eine, zwei oder bis zu drei Spalten.
- Bricht lange VM-/LXC-Namen sicher um und begrenzt Status-Badges auf mobilen
  Ansichten.
- Blendet unbekannte OS-Werte aus, statt `unknown unknown` anzuzeigen, und
  entfernt die doppelte Read-only-Anzeige.
- Ergänzt Regressionen für wiederholte `hass`-Updates, lange Namen und
  unbekannte Sensorwerte.

## 0.1.0-beta.8 – Lovelace-Entitätsdaten und Status (Kandidat)

- Erkennt VMs und LXC-Container anhand ihrer tatsächlichen Attribute und nicht
  nur anhand historischer Entity-ID-Präfixe.
- Zeigt vorhandene freie Ressourcenwerte an, ohne fehlende CPU-, RAM- oder
  Speicherwerte zu simulieren.
- Trennt Agent-Verbindung, Hostzustand sowie unbekannte/offline Fehlerzustände.
- Ergänzt Regressionen mit anonymisierten Live-Entitätsstrukturen.

## 0.1.0-beta.7 – Robuste Lovelace-Spracherkennung (Kandidat)

- Behebt den iPhone-Editorfehler `locale?.toLowerCase is not a function`.
- Verwendet eine zentrale, typgeprüfte Sprachauflösung mit Priorität für
  `hass.language`, sicherer Unterstützung von `hass.locale` als String oder
  Objekt und englischem Fallback.
- Ergänzt Regressionen für Karte, Vorschau, Editor, fehlendes `hass` sowie
  deutsche und englische Sprachwerte.

## 0.1.0-beta.6 – Lovelace editor layout and preview fix (Candidate)

- Add responsive editor layout with localized German/English labels.
- Preserve card preview sizing and render an explicit offline/empty state.
- Add a Home Assistant editor-contract harness for picker, preview, save, and
  reopen lifecycle coverage.

## 0.1.0-beta.5 – Lovelace mobile editor fix (Candidate)

- Keep the editor DOM stable during `setConfig()` updates so mobile focus and
  unsaved input survive Home Assistant background updates.
- Add iPhone/iPad Playwright coverage for empty/unknown entities, browser errors,
  failed requests, and the editor lifecycle.

## 0.1.0-beta.4 – Lovelace-Dashboard (Prerelease)

- Read-only Lovelace-Karte für Proxmox-Host, VMs, LXC-Container und
  Wartungshinweise ergänzt.
- Host-, VM- und LXC-Messwerte werden aus den tatsächlich vorhandenen HA-
  Entitäten erkannt; fehlende Daten werden nicht simuliert.
- Karte wird beim Laden der Integration automatisch als versionierte
  Frontend-Ressource registriert und ist über den grafischen Karteneditor
  auswählbar.
- Responsive Light-/Dark-Mode-Darstellung und deutsche/englische Texte ergänzt.
- Als GitHub-Prerelease veröffentlicht; eine produktive Installation ist nicht
  erfolgt.

## 0.1.0-beta.3 – Private HTTPS-IP-Transport (lokaler Kandidat)

- Private HTTPS-Ziele einschließlich IP-Adressen mit aktivierter
  Zertifikats- und IP-SAN-Prüfung unterstützt.
- CA-Dateien sind auf `/ssl/` begrenzt; HTTP- und unsichere TLS-Fallbacks bleiben
  ausgeschlossen.
- Nicht veröffentlicht und nicht in produktivem Home Assistant installiert.

## Unreleased – Phase 4.6 Agent-Runtime

- lesender Proxmox-HTTPS-Client für Host, LXC und VMs mit TLS-, Größen- und
  Authentifizierungsprüfung
- TOML-basierter Agent-Startpunkt mit getrennten systemd-Credentials und
  read-only Runtime-Verdrahtung
- Installer um Proxmox-URL, CA, Knoten und geschütztes API-Credential ergänzt
- Update- und Shell-Ausführung bleibt deaktiviert

## Unreleased – Phase 4.4 Vorbereitung

- Read-only Proxmox-Inventory-Backend mit injizierbarem Client für LXC und VMs
- TLS-erzwingender Agent-Server mit Bearer-Authentifizierung und systemd-
  Credential-Laden vorbereitet
- Keine Update- oder Shell-Ausführung ergänzt; produktiver Listener bleibt
  unimplementiert/ungeinstalliert

## Unreleased – Phase 4.5 Installer-Vorbereitung

- reproduzierbare Installations-, Prüf-, Update- und Deinstallationsskripte
- exakte Commit-Prüfung, TLS-/DNS-Gates und geschützte systemd-Credentials
- standardmäßig kein Apply, kein Start und kein automatischer Neustart

## 0.1.0-beta.2 – Config-Flow-Fix

- Config Flow funktioniert als eigenständiges Home-Assistant-Paket ohne das
  separate Agent-Paket.
- HTTP-Transport innerhalb der Integration gebündelt; keine unzulässigen
  Laufzeitimporte aus `agent`.
- Regressionstest für den isolierten Installationsfall ergänzt.
- Passive Beta bleibt read-only; Updateausführung bleibt deaktiviert.

## 0.1.0-beta.1 – Passive Beta

- Read-only Home-Assistant-Integration, Agent-Kern und Lovelace-Karte
- Offline-Discovery, API-Verträge, Jobverwaltung und Sicherheitsgates
- Updateausführung global deaktiviert
- Installation der Karte aus derselben Version als lokale HA-Ressource
- Keine produktive Geräte- oder Infrastrukturaktion
## 0.1.0-beta.10 – Scroll- und DOM-Stabilität (Prerelease veröffentlicht)

- Behebt den iPhone-Scrollsprung durch einmaligen Shadow-DOM-Aufbau und
  inkrementelle Updates bestehender Knoten.
- Bewahrt aufgeklappte Hostbereiche sowie die DOM-Identität von VM- und
  Containerkarten während wiederholter `hass`-Aktualisierungen.
- Ergänzt eine reproduzierbare Scroll-Regression mit drei unabhängigen
  Karteninstanzen sowie iPhone-, iPad- und Desktop-Browser-Matrix.
- Keine automatische Installation, kein HA-Neustart und keine Änderungen an
  Proxmox oder Agent.
## 0.1.0-beta.19 – passive update status clarity (candidate)

### Deutsch

- Unterscheidet `unsupported`, `unauthorized`, `not_checked`, `error`,
  `stale`, `current` und `updates_available` im API-Vertrag und in der Karte.
- Ergänzt eine eng begrenzte, optionale Allowlist für ausdrücklich autorisierte
  Debian-/Ubuntu-APT-Gastziele; sie verändert keine produktive Konfiguration.
- Zeigt Updateanzahl, Sicherheitsupdates, Prüfzeitpunkt und Fehler verständlich
  an. Ungeprüfte oder nicht unterstützte Ziele werden nicht als aktuell bewertet.
- Beta.19 enthält weiterhin keine echte Updateausführung und keine automatische
  Paketlistenaktualisierung.

### English

- Preserves explicit update states in the API and Lovelace card instead of
  collapsing unsupported, unauthorized, not-checked, error, and stale results
  into one generic label.
- Adds a tightly allowlisted opt-in format for explicitly authorized
  Debian/Ubuntu APT guest targets without changing production configuration.
- Displays update counts, security updates, check time, and errors clearly.
- Real update execution and automatic package-index refresh remain disabled.
## 0.1.0-beta.20 – Updateverwaltung ohne Ausführung

### Deutsch

- Passive Update-Erkennung liest ausschließlich vorhandene APT-Cache-Daten;
  der ausdrücklich angeforderte Dry Run bleibt ein getrennt validierter Pfad.
- LXC-Ziele sind standardmäßig nicht autorisiert; nur eine explizite Allowlist
  kann ein laufendes Debian-/Ubuntu-Ziel freigeben. Gestoppte Container werden
  nicht gestartet oder angesprochen.
- Paketname sowie installierte und verfügbare Versionen werden angezeigt;
  Sicherheitsklassifizierungen bleiben unbekannt, wenn die Datenquelle sie
  nicht belastbar liefert.
- Der sichtbare Button „Updates installieren“ ist dauerhaft deaktiviert und
  serverseitig nicht implementiert.

### English

- Passive update detection reads existing APT cache data only; the explicitly
  requested dry run remains a separate, validated path.
- LXC targets are unauthorized by default; only an explicit allowlist can
  authorize a running Debian/Ubuntu target. Stopped containers are never
  started or probed.
- Package names and installed/available versions are exposed; security
  classification remains unknown when the source cannot prove it.
- The visible “Install updates” button is permanently disabled and has no
  server-side execution route.
## 0.1.0-beta.25 – Agent-Lifecycle und Port-Bind-Race (Prerelease)

### Deutsch

- Der externe Agent beendet seinen HTTPS-Server bei `SIGTERM`/`SIGINT` jetzt
  kontrolliert und schließt den Listen-Socket garantiert.
- Der Updater prüft nach dem Dienststopp die tatsächliche Freigabe von Port
  48128, bevor der Agent-Baum ausgetauscht oder ein neuer Prozess gestartet
  wird. Ein belegter Port bricht sicher ab.
- `TimeoutStopSec=30` begrenzt den systemd-Stopp; historische und fehlgeschlagene
  Rollback-Stagings bleiben erhalten.

## Nächster Beta-Kandidat – Port-Bind-Forensik

### Deutsch

- Der Updater prüft für Port 48128 neben `LISTEN` auch aktive TCP-Zustände und
  bestätigt, dass die systemd-Unit tatsächlich inaktiv ist. Der terminale,
  kernelverwaltete `TIME-WAIT`-Zustand wird bei `SO_REUSEADDR` nicht als
  blockierender Listener behandelt.
- Vor und nach Stopp, Swap und Start werden ausschließlich nicht-sensitive
  MainPID-, ControlPID-, Cgroup- und Socketdaten protokolliert.
- Die vorhandenen Journale beweisen den wiederholten Bind-Fehler, aber nicht
  mehr nachträglich die historische Halter-PID. Diese Unsicherheit bleibt
  ausdrücklich dokumentiert.

### English

- Before swapping the agent tree, the updater checks all TCP states for port
  48128, not only `LISTEN`, and confirms that the systemd unit is inactive.
- Non-sensitive MainPID, ControlPID, cgroup, and socket diagnostics are logged
  around stop, swap, and start.
- Existing journals prove the repeated bind failure but cannot recover the
  historical holder PID after the fact; that uncertainty is documented.

### English

- The external agent now shuts down its HTTPS server explicitly on
  `SIGTERM`/`SIGINT` and always closes the listening socket.
- After stopping the service, the updater verifies that port 48128 is really
  free before swapping the agent tree or starting a new process. A still-busy
  port causes a safe abort.
- `TimeoutStopSec=30` bounds the systemd stop; historical and failed rollback
  staging directories remain preserved.
## 0.1.0-beta.26 – Port-Gate-Forensik und sichere Upgrade-Rennen (Prerelease)

### Deutsch

- Der Updater blockiert aktive TCP-Zustände und eine noch aktive systemd-Unit
  auf Port 48128; ausschließlich der terminale, kernelverwaltete `TIME-WAIT`
  Zustand wird bei `SO_REUSEADDR` ausgenommen.
- Eine zweite Port-/Unit-Prüfung unmittelbar vor `systemctl start` schließt das
  Stop-/Swap-/Start-Rennen. PID-, ControlPID-, Cgroup- und Socket-Diagnose wird
  nicht-sensitiv an den relevanten Übergängen protokolliert.
- Die isolierten Regressionen decken freien Port, Listener, verzögerten
  Shutdown, Doppelstart und `TIME-WAIT` ab. Beta.24-Planvergleich und Beta.25-
  Lifecycle-Fix bleiben enthalten; Rollback-Schutz und gesperrte produktive
  Updatepfade bleiben unverändert.

### English

- The updater blocks active TCP states and an active systemd unit on port 48128;
  only terminal kernel-owned `TIME-WAIT` is exempted for the server's
  `SO_REUSEADDR` bind.
- A second port/unit check immediately before `systemctl start` closes the
  stop/swap/start race. PID, ControlPID, cgroup, and socket diagnostics remain
  non-sensitive at the relevant transitions.
- Isolated regressions cover a free port, active listener, delayed shutdown,
  duplicate start, and `TIME-WAIT`. The Beta.24 plan comparison and Beta.25
  lifecycle fix remain included; rollback protection and locked production
  update paths are unchanged.

## Nächster Beta-Kandidat – Readiness erkennt Restart-Races

### Deutsch

- Der Updater merkt sich den systemd-Restartzähler vor dem Agent-Austausch.
- Jeder automatische `Restart=on-failure`-Versuch während der neuen
  Readiness wird als fehlgeschlagener Upgrade-Start behandelt, selbst wenn
  ein späterer Versuch noch gesund wird.
- Der bestehende Rollback bewahrt den vorherigen Code und die Diagnose; die
  Schutzprüfung wird nicht durch längere Wartezeiten ersetzt.

### English

- The updater records the systemd restart counter before exchanging the agent.
- Any automatic `Restart=on-failure` attempt during readiness is treated as a
  failed upgrade start, even if a later attempt becomes healthy.
- Existing rollback preserves the previous code and diagnostics; the safety
  gate is not replaced by a longer timeout.
## 0.1.0-beta.27 – Restart-Race-Erkennung (Prerelease)

### Deutsch

- Der Updater erfasst den systemd-Restartzähler vor dem Agent-Austausch und
  nochmals unmittelbar nach dem erfolgreichen TLS-/API-Healthcheck.
- Jeder Restart-Anstieg wird als fehlgeschlagener Start behandelt und führt
  zum bestehenden sicheren Rollback; wiederholte Bind-Fehler können nicht mehr
  durch einen später erfolgreichen systemd-Versuch als Exit 0 verdeckt werden.
- Die konkrete Beta.22→Beta.26-Socket-Semantik mit `TIME-WAIT` und fehlendem
  `SO_REUSEADDR` ist als isolierte Regression dokumentiert.

### English

- The updater records the systemd restart counter before the agent swap and
  again immediately after a successful TLS/API healthcheck.
- Any restart increase is treated as a failed start and activates the existing
  safe rollback; repeated bind failures can no longer be hidden by a later
  successful systemd attempt returning exit 0.
- The concrete Beta.22→Beta.26 socket semantics involving `TIME-WAIT` and
  missing `SO_REUSEADDR` are covered by an isolated regression.
