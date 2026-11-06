# Smart Homelab Maintenance

Read-only Home-Assistant-Integration, Lovelace-Karte und offline testbarer
Wartungsagent für private Homelab-Umgebungen.

## Status

Beta-5-Kandidat; Veröffentlichung erst nach vollständiger CI.
Updateausführung ist deaktiviert. Agent-,
Proxmox- und Containerzugriffe müssen vor einer späteren Aktivierung separat
konfiguriert und geprüft werden.

## Bestandteile

```text
custom_components/smart_homelab_maintenance/  Home-Assistant-Integration
frontend/                                     Lovelace-Karte
agent/                                        Offline-Agent-Kern
tests/                                        Offline- und Laufzeittests
docs/                                         öffentliche technische Doku
```

## Installation

Die Karte ist im Integrationspaket enthalten. Beim Laden der Integration wird
sie als versionierte Frontend-Ressource registriert und im Lovelace-
Karteneditor angeboten; eine manuelle YAML-Ressource ist dafür nicht nötig.

1. Für die Integration das Repository als Marketplace-/HACS-Integration
   einbinden und `custom_components/smart_homelab_maintenance/` installieren.
2. Die Karte im Lovelace-Karteneditor als `Smart Homelab Maintenance` auswählen.
3. Erst danach die Integration über den Config Flow mit einer privaten
   HTTPS-Agent-Adresse und vertrauenswürdiger Zertifikatskette verbinden.

Der spätere Proxmox-Installationsweg ist in
[`docs/AGENT_INSTALLATION.md`](docs/AGENT_INSTALLATION.md) beschrieben. Die
Skripte arbeiten standardmäßig nur im Prüfmodus und starten keinen Dienst.

Für eine spätere Veröffentlichung müssen die Marketplace-Struktur, die
Release-Artefakte und der Installationsweg erneut gegen die Zielversion von
Home Assistant geprüft werden.

## Sicherheit

- passive Beta; keine Updateausführung
- keine freien Shell-Kommandos über die API
- Agent-Kommunikation nur über private HTTPS-Ziele, authentifiziert und
  größen-/timeoutbegrenzt
- unbekannte oder blockierte Anwendungen bleiben lesend
- Zugangsdaten gehören ausschließlich in die lokale Konfiguration und dürfen
  nicht in Logs, Issues, Screenshots oder Diagnosen erscheinen
- der Agent-Server erzwingt TLS, bindet nicht an unbeschränkte Adressen und
  nutzt getrennte systemd-Credentials; das Proxmox-Backend arbeitet nur lesend
- produktive Installation und Start sind nicht erfolgt

## Entwicklung und Tests

Die Tests verwenden Mock-Daten und lokale Fixtures. Details stehen in
`docs/architecture.md`, `docs/security.md` und `docs/testing.md`.

## Lizenz

MIT – Copyright (c) 2026 Michael Dick
