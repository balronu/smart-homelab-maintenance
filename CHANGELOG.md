# Changelog

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
