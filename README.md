# Smart Homelab Maintenance

Read-only Home-Assistant-Integration, Lovelace-Karte und offline testbarer
Wartungsagent für private Homelab-Umgebungen.

## Beta.20: vollständige Updateverwaltung ohne Ausführung

Dieser Entwicklungsstand trennt die passive APT-Cache-Auswertung vom bewusst
angeforderten Dry Run. Nur ausdrücklich allowlistete, laufende Debian-/Ubuntu-
Ziele können später geprüft werden; VMs ohne autorisierten Gastzugriff und
gestoppte LXCs werden nicht angesprochen. Der Button **Updates installieren**
ist sichtbar, dauerhaft deaktiviert und besitzt keinen Serviceaufruf. Echte
Updateausführung bleibt auch bei manipulierten Frontend-Anfragen serverseitig
gesperrt.

Die zweisprachigen Release Notes liegen unter
[`docs/releases/v0.1.0-beta.20.md`](docs/releases/v0.1.0-beta.20.md). Beta.20
ist als Prerelease veröffentlicht; der Agent wird weiterhin separat aktualisiert.

## Beta.21: sicherer LXC-Gastzugriff

Der Beta.21-Kandidat ergänzt einen optionalen, root-seitigen Unix-Socket-Helper
für ausdrücklich allowlistete LXC-Ziele. Der Helper akzeptiert ausschließlich
die festen Operationen `read` und `simulate`, prüft die CT-Allowlist bei jeder
Anfrage und lehnt alle anderen Befehle, Pfade und Ziele ab. Der Agent bleibt
standardmäßig deaktiviert (`lxc_helper_enabled = false`); eine bloße HACS-
oder Agent-Aktualisierung aktiviert den Gastzugriff nicht. Beta.21 ist als
GitHub-Prerelease veröffentlicht. Details und die
separaten Freigabegates stehen in
[`docs/lxc-apt-helper.md`](docs/lxc-apt-helper.md) und
[`docs/security.md`](docs/security.md).

## Beta.19: Dry Runs und passive Update-Erkennung

Beta.19 behebt den Lovelace-Aufruf für `smart_homelab_maintenance.dry_run`:
Die Karte fordert die verpflichtende Home-Assistant-Serviceantwort an und
zeigt Paketänderungen, Warnungen, Sicherheitsbewertung, Fehler und
Zeitüberschreitungen sichtbar an. Die passive Update-Erkennung bewahrt
außerdem die eindeutigen Zustände aktuell, Updates verfügbar, noch nicht
geprüft, nicht unterstützt, nicht autorisiert, fehlgeschlagen, veraltet und
unbekannt. Echte Updates bleiben deaktiviert.

Der separate Agent-Updater ist gegen einen
Restart-/Readiness-Race gehärtet: Der TLS-Healthcheck wird innerhalb eines
begrenzten Zeitfensters wiederholt, ein Fehler führt über einen EXIT-sicheren
Rollbackpfad zurück zum vorherigen Agent-Code, und Rollback-Staging wird nicht
automatisch gelöscht. Diese Korrektur ist in Beta.20 enthalten; der produktive
Agent muss separat auf eine kompatible Agent-Version aktualisiert werden.

## Beta.18: gemeinsamer Versions- und Updatevertrag

Integration, Karte und Agent tragen dieselbe Beta-Version. Der Agent meldet
zusätzlich den API-Vertrag über `/api/v1/health`. Home Assistant bewertet die
Kombination als `current`, `outdated`, `incompatible` oder `unknown` und zeigt
die Abweichung sichtbar an. Ein HACS-Update aktualisiert niemals automatisch
den separat laufenden Agenten.

Der vorbereitete Agent-Prozess in `scripts/upgrade-agent.sh` prüft Commit,
Quellintegrität, TLS-CA, Dienst und Healthcheck. Der mutierende Pfad benötigt
explizit `--apply --confirm`, hält während des Healthchecks einen temporären
Rollback-Stand vor und stellt ihn bei einem fehlgeschlagenen Healthcheck
wieder her. Er verändert weder Proxmox, VMs noch LXCs.

## Status

Beta.21-Prerelease: Der optionale root-seitige LXC-Helper prüft Peer-UID,
Allowlist, feste Operationen, Laufstatus, Timeout und Ausgabelimit pro Anfrage.
Der Helper ist nicht installiert oder aktiviert; echte Paketupdates bleiben
serverseitig gesperrt. Die zweisprachigen Release Notes stehen in
[`docs/releases/v0.1.0-beta.21.md`](docs/releases/v0.1.0-beta.21.md).

Beta.19-Prerelease: Dry-Run-Serviceantworten und passive Update-Erkennung
sind veröffentlicht. Der Dry-Run-Button verarbeitet den verpflichtenden
Service-Response-Vertrag; die Update-Zustände werden nicht als „aktuell“
fehlklassifiziert. Die vollständige Beschreibung steht in
[docs/releases/v0.1.0-beta.19.md](docs/releases/v0.1.0-beta.19.md).

Beta.18-Prerelease: gemeinsamer Versions-/API-Vertrag für Integration, Karte
und Agent sowie ein ausdrücklich bestätigungspflichtiger Agent-Updatepfad.
Die responsive Lovelace-Karte behält stabile dynamische Höhe, aufklappbare
Host-/VM-/LXC-Details und ein Größenänderungssignal für das Home-Assistant-
Sections-Layout. Eine echte iOS-Home-Assistant-Praxisprüfung steht noch aus;
der Scrollfehler ist nicht als behoben bestätigt.
Letzter veröffentlichter Release: [v0.1.0-beta.18](https://github.com/balronu/smart-homelab-maintenance/releases/tag/v0.1.0-beta.18).

Die passive Update-Erkennung unterscheidet explizit aktuell, Updates
verfügbar, noch nicht geprüft, nicht unterstützt, nicht autorisiert,
fehlgeschlagen, veraltet und unbekannt. Die ausführliche deutsch/englische
Beschreibung steht in [docs/update-detection.md](docs/update-detection.md).

Passive update detection explicitly distinguishes current, updates available,
not checked, unsupported, unauthorized, failed, stale, and unknown states. See
[docs/update-detection.md](docs/update-detection.md).
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
