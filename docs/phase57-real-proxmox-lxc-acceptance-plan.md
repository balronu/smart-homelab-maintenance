# Phase 57 – echte Proxmox-LXC-Abnahme vorbereiten

**Stand:** 2026-11-09 · **RC:** `v1.0.0-rc.1` · **Referenz-Merge-Commit:**
`3d2125347303bd302e1e7a022d066f959c5d998d`

Dieses Dokument ist ein Aufbau- und Freigabeplan. Es provisioniert keinen
Host, erstellt keinen LXC und führt keine Pakettransaktion aus. `pve-home`,
VM104 und produktive LXCs bleiben vollständig außerhalb des Testpfads.

## Ergebnis der Machbarkeitsprüfung

| Option | `pct`/echtes LXC | Bewertung |
|---|---:|---|
| GitHub-hosted Actions | Nein | Für Phase 56 geeignet; verschachtelte Virtualisierung ist laut GitHub nicht offiziell unterstützt und daher kein Proxmox-Nachweis. |
| Cloud-VM mit Nested Virtualization | Bedingt | Technisch möglich bei ausdrücklich unterstützten VM-Typen, aber zusätzlicher Hypervisor-, Netzwerk- und Kostenpfad. Kein kostenloser, bereits freigegebener Pfad bekannt. |
| Temporärer Bare-Metal-Server | Ja | Bevorzugt: Proxmox läuft direkt auf Hardware, `pct` und LXC-Kernelpfad sind real. Erfordert Bestellung, Zugang und sichere Löschung. |
| Lokaler Container/chroot | Nein | Kann Debian/APT/systemd/helper testen, ersetzt aber weder Proxmox-IPC noch `pct` oder einen echten LXC-Namespace. |

GitHub Actions bleibt dauerhaft als Regressionstest erhalten. Die bestehende
Phase-56-Dokumentation benennt die Grenze ausdrücklich: der feste `pct`-Adapter
ist kein echter Proxmox-Pfad.

### Empfohlene externe Umgebung

Ein **kurzzeitig gemieteter dedizierter Bare-Metal-Server** mit mindestens
4 vCPU, 16 GB RAM und 100 GB SSD, ausschließlich für diesen Test. Darauf wird
Proxmox VE direkt installiert, ein isoliertes Testnetz angelegt und genau ein
Debian-LXC betrieben. Proxmox VE selbst ist als AGPLv3-Software frei nutzbar;
eine Community-Subscription ist optional und wird für diesen Test nicht
vorausgesetzt. Die Providerwahl und Bestellung benötigen eine separate
Freigabe.

Als aktuelle Kostengröße dient ein offizielles OVHcloud-Angebot: dedizierte
Advance-Server beginnen dort mit **114,99 € netto/Monat**; ein passender
konkreter Konfigurationspreis kann durch Installation, Region und Laufzeit
höher liegen. Dazu kommen gegebenenfalls VAT, eine Installationsgebühr und
eine optionale Proxmox-Subscription von **120 €/CPU-Socket/Jahr**. Für einen
kurzen Test ist deshalb konservativ mit **ca. 150–300 € netto im ersten Monat**
zu rechnen; das ist eine Budgetschätzung, keine Bestellung oder Preiszusage.

## Freigabe- und Isolationsgates

Vor jeder Provisionierung müssen alle Punkte schriftlich bestätigt sein:

1. Neuer Anbieter-Account oder dedizierte Testinstanz; keine Verbindung zu
   `pve-home`, VM104, Home Assistant oder dem Heimnetz.
2. Anbieter-Firewall: nur temporäre Admin-Quelle und ein ausdrücklich
   benötigter Testzugang; kein öffentliches HA-/Agent-API.
3. Keine produktiven Credentials, Zertifikate, Backups, Snapshots, Grants oder
   Policies kopieren. Für Proxmox wird ein nur dort gültiger Test-Token mit
   Ablaufdatum verwendet.
4. `execution_enabled=false` bleibt während Installation und Readiness-Checks
   unverändert. Das Aktivieren gilt nur für den ausdrücklich begrenzten
   Testlauf und wird danach zurückgesetzt bzw. der gesamte Server verworfen.
5. CTID, Hostname, DNS, Storage und Bridge tragen einen eindeutigen
   `phase57-test`-Namensraum. Kein Autostart und kein produktiver Mount.
6. Vor dem ersten Mutationslauf wird ein Operator-Stopppunkt dokumentiert;
   ohne gesonderte Freigabe bleibt Phase D (echte Paketinstallation) **NOT RUN**.

## Reproduzierbarer Aufbau

### 1. Proxmox-Testknoten

- Proxmox-VE-ISO und SHA256 aus der offiziellen Downloadquelle beziehen.
- Bare-metal installieren; ausschließlich die Testdisk verwenden.
- Einen einzelnen Node ohne Cluster/HA einrichten.
- Managementzugriff auf eine temporäre Admin-Quelle begrenzen.
- Eine isolierte Bridge ohne Route in das Heimnetz anlegen. Für die
  Paketquelle wird ein lokaler HTTP- oder `file:`-Pfad im Test-LXC verwendet;
  externe APT-Repositories sind nicht erforderlich.
- Debian-12-Template mit verifiziertem Digest importieren.
- Einen **unprivilegierten** CT mit systemd, keinem Bind-Mount, keinem
  Device-Passthrough, `onboot=0` und genau einer Test-Bridge erstellen.
  Falls der konkrete Helper einen anderen Modus zwingend benötigt, ist das ein
  dokumentierter Blocker und keine stillschweigende Privilegierung.

### 2. Agent, Helper und temporäre Rechte

- RC1-Quellstand und Installer auf dem Testnode anhand Commit/Hash prüfen.
- Agent und root-owned Helper nach `docs/AGENT_INSTALLATION.md` installieren;
  `systemd-analyze verify`, Besitzer/Modi, Socket-Peer-Credentials und
  Allowlist vor dem Start read-backen.
- `agent.toml` mit einem Test-Proxmox-Endpunkt, Test-CA und
  `execution_enabled=false` einrichten. Tokens nur über systemd
  `LoadCredential`, niemals in Git, Logs, Screenshots oder Artefakten.
- Dynamische Discovery gegen den Testnode ausführen. Nur der neue CTID darf
  nach manueller Prüfung in die temporäre Allowlist aufgenommen werden.
- Simulation-Grant und Update-Grant getrennt setzen, jeweils über die API und
  mit persistentem Read-back. Keine Wildcards, keine Inventar-Automation.

### 3. Testpaket und genau eine Mutation

Auf einem separaten Build-Arbeitsverzeichnis werden zwei lokale Debian-Pakete
mit identischem Namen gebaut: `smh-e2e-fixture` Version `1.0` und `2.0`.
Version 1.0 wird als **Setup-Schritt** in den Wegwerf-LXC gebracht; dieser
Schritt zählt nicht als Abnahme-Mutation und wird separat protokolliert.

Der eigentliche Abnahmelauf ist ausschließlich `1.0 → 2.0`:

1. Discovery und Eligibility lesen den laufenden CT dynamisch.
2. Simulation liefert Paketname, Alt-/Neu-Version, Digest und Paketdetails.
3. Update-Grant wird separat bestätigt.
4. Eine unmittelbar vorherige Simulation erzeugt den finalen Plan.
5. Der stale-plan-Test verändert danach bewusst nur die Planbasis und muss die
   Mutation ablehnen.
6. Nach erneuter gültiger Simulation bestätigt der Operator genau **eine**
   Installation. Der Agent ruft den festen Helper auf; der Helper ruft den
   echten `pct exec <CTID> -- ...`-Pfad auf.
7. Job-ID, Events, Exit-Code 0, Postcheck und Paketversion 2.0 werden aus API,
   persistenter Jobablage und Gast-`dpkg-query` korreliert.
8. Update- und Simulation-Grants werden widerrufen und per API/Helper-Readback
   nachgewiesen. Kein Reboot und keine automatische Wiederholung.

Die Testdokumentation muss den Setup-Installationsschritt und die eine
Abnahme-Mutation zeitlich und technisch getrennt ausweisen.

## Testmatrix

| ID | Szenario | Erwarteter Nachweis |
|---|---|---|
| P01 | Node/CT Discovery | echter Proxmox-Node, dynamische CTID, running, Debian/APT |
| P02 | Simulation/Details | feste Helper-Operation, Paketliste, Digest, keine Mutation |
| P03 | Grant-Trennung | Simulation ohne Update; Update ohne Simulation wird abgewiesen |
| P04 | Stale Plan | geänderte Paketbasis/Digest blockiert vor `pct exec` |
| P05 | Einmalige Installation | `1.0→2.0`, Job-ID/Eventfolge, Exit 0, Postcheck |
| P06 | Widerruf | beide Grants entfernt; neuer Lauf fail-closed |
| P07 | Helper-Ausfall | Socket/Unit kontrolliert stoppen; Status `unknown`/blocked, keine Mutation |
| P08 | Timeout/unklarer Prozess | begrenzter Testlauf, Recovery-Sperre, keine Retry-Schleife |
| P09 | Recovery-Sperre | `manual_recovery_required`; keine automatische Reparatur, kein Reboot |
| P10 | Recreate/cleanup | CT stoppen/entfernen, Test-Token widerrufen, Server löschen |

P07–P09 werden in frischen, wegwerfbaren CT-Zuständen ausgeführt. Es wird
keine produktive dpkg-Datenbank beschädigt; `apt --fix-broken`,
`dpkg --configure -a`, automatische Reparatur und automatische Wiederholung
sind ausdrücklich verboten.

## Mobile Abnahmecheckliste

Für jede Kombination wird ein Screen-Recording oder eine nummerierte
Screenshot-Serie mit Zeitstempeln im Testsystem erstellt; keine produktiven
Tokens oder Gastdaten dürfen sichtbar sein.

### iPhone

- [ ] Hochformat: initiale Scrollposition, Kartenkopf und Zielstatus sichtbar.
- [ ] Touchziele ohne Zoom bedienen; Simulation und Update-Grant sind getrennte
      Aktionen.
- [ ] Bestätigungsdialog vollständig lesen; Abbrechen und erneutes Öffnen prüfen.
- [ ] Finale Simulation, Paketdetails und eindeutige Einmal-Bestätigung prüfen.
- [ ] Job-ID, Fortschritt, Exit-Code 0 und Postcheck ohne horizontales Scrollen
      ablesbar.
- [ ] Helper-Ausfall/Recovery-Sperre zeigt eine blockierende Fehlermeldung;
      kein Installations- oder Retry-Button darf aktiv bleiben.

### iPad Hochformat

- [ ] Dieselben Schritte wie auf dem iPhone mit größerem Layout prüfen.
- [ ] Keine doppelte Aktionsleiste, abgeschnittene Dialogbuttons oder
      unerreichbare Widerrufsaktion.
- [ ] Scrollposition nach Jobstatus-Refresh bleibt verständlich und springt
      nicht vor die Sicherheitsbestätigung.

### iPad Querformat

- [ ] Breites Layout: keine verdeckten Spalten, keine abgeschnittenen
      Paketversionen, keine unlesbaren Statuslabels.
- [ ] Dialoge bleiben zentriert und Touchziele sind der sichtbaren Aktion
      eindeutig zugeordnet.
- [ ] Fehlerstatus, manuelle Recovery-Sperre und Grant-Widerruf bleiben auch
      bei geteilter Karten-/Detailansicht erreichbar.

Für alle Geräte gilt: kein Doppeltippen darf zwei Jobs erzeugen; nach
Abschluss wird die persistente Job-ID erneut geladen. Die Checkliste ist eine
Vorbereitung und kein Nachweis einer bereits durchgeführten mobilen Abnahme.

## CI, Risiken und Entscheidung

- Die bestehenden PR-/Main-Gates und Phase-56-Actions bleiben unverändert und
  werden in einem separaten Docs-PR erneut geprüft.
- Ein Docs-PR autorisiert weder Merge noch Release noch Testnode.
- Hauptrisiken sind Nested-Virtualization-Abweichungen, öffentliche
  Fehlkonfiguration des Testnodes, unvollständige Proxmox-API-ACLs und eine
  nicht realistisch reproduzierte Recovery-Situation.
- **GO:** für diesen reproduzierbaren Vorbereitungsplan und einen separaten
  Docs-PR.
- **NO-GO:** für Bestellung/Provisionierung, echte Paketinstallation,
  Produktivfreigabe und mobile Abnahme, bis Kosten, Anbieter, Testzugang und
  Phase-D-Freigabe separat bestätigt sind.

### English summary

This is a preparation plan only. The preferred option is a short-lived,
dedicated bare-metal Proxmox node with one unprivileged Debian LXC on an
isolated network. GitHub-hosted Actions remain valuable for Debian/APT/
systemd/helper regression coverage but cannot prove real `pct`/LXC behavior.
No provider resource, package mutation, production grant, credential, VM104,
or `pve-home` system was used or changed.
