# Smart Homelab Maintenance

Read-only Home-Assistant-Integration, Lovelace-Karte und offline testbarer
Wartungsagent für private Homelab-Umgebungen.

## Status

Beta.17-Fix-Kandidat: responsive Lovelace-Karte mit stabiler dynamischer Höhe,
aufklappbaren Host-/VM-/LXC-Details und einem Größenänderungssignal für das
Home-Assistant-Sections-Layout. Eine echte iOS-Home-Assistant-Praxisprüfung
bleibt vor Veröffentlichung erforderlich; der Scrollfehler ist nicht als
behoben bestätigt.
Letzter veröffentlichter Release: [v0.1.0-beta.16](https://github.com/balronu/smart-homelab-maintenance/releases/tag/v0.1.0-beta.16). Beta.17 ist noch nicht veröffentlicht.
Der abschließende Praxistest in der Home-Assistant-iOS-App steht noch aus.
Updateausführung ist deaktiviert. Agent-,
Proxmox- und Containerzugriffe müssen vor einer späteren Aktivierung separat
konfiguriert und geprüft werden.

Beta.17 enthält passive Paketprüfungen für nachweislich unterstützte
Debian-/Ubuntu-Ziele und einen ausdrücklich bestätigten `apt-get --simulate`
Dry Run. Paketlisten werden nicht aktualisiert, Pakete werden nicht installiert
und Systeme werden nicht neu gestartet. Eine spätere Ausführung bleibt
serverseitig gesperrt und benötigt eine eigene, separat freizugebende Phase;
ein deaktivierter UI-Button allein wäre keine Sicherheitsgrenze.

Beta.16 isoliert Fehler der optionalen Update-Abfrage vom Kerninventar. Wenn
der Update-Endpunkt ausfällt, bleiben Host, VMs und LXCs sichtbar und der
Updatezustand wird als unbekannt gemeldet. Intervall-Refreshes werden über den
thread-sicheren Home-Assistant-Scheduler eingeplant.

Beta.17 ergänzt einen versionierten Agent-Healthcheck und eine robuste
Ressourcenprojektion. Fehlende Proxmox-Werte werden nicht als null erfunden;
VM-Gast-Freiräume werden nur angezeigt, wenn eine Datenquelle sie tatsächlich
liefert. Host, VM und LXC-Ressourcen sind in der Karte eindeutig beschriftet.
Für korrekte Beta.17-Ressourcen müssen Home-Assistant-Integration und der
separat laufende Wartungsagent gemeinsam auf Beta.17 aktualisiert werden;
nur die HACS-Integration zu aktualisieren ersetzt den Agenten nicht.

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
