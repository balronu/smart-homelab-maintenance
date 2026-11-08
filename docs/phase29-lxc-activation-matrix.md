# Phase 29: LXC-Eignungs- und Aktivierungsmatrix

Stand: 2026-11-08. Diese Matrix ist eine passive Bestandsaufnahme und keine
Produktivfreigabe. Es wurden keine Gastbefehle, `pct exec`, Starts,
Allowlist-Änderungen oder Helper-Aktivierungen durchgeführt.

## Passive Befunde

Proxmox meldet für alle zehn Container `ostype=debian`. Eine Debian-Version,
`apt`/`dpkg`-Verfügbarkeit und der Paketplan konnten aus den vorhandenen
Proxmox-Metadaten nicht nachgewiesen werden, weil die LXC-Rootfs nicht passiv
gemountet vorlagen. Diese Werte bleiben daher **UNKNOWN** und werden nicht als
Eignungsnachweis verwendet.

| CTID | Name | Zustand | Proxmox-OS | Version/APT | Risiko-/Besonderheit | Aktueller Status |
|---:|---|---|---|---|---|---|
| 101 | cloudflared | laufend | Debian konfiguriert | UNKNOWN | Netzwerk-/Edge-Dienst | nicht autorisiert |
| 102 | zigbee2mqtt-haus | laufend | Debian konfiguriert | UNKNOWN | Hausautomatisierung | nicht autorisiert |
| 103 | mariadb | laufend | Debian konfiguriert | UNKNOWN | Datenbank, migrationssensitiv | nicht autorisiert |
| 105 | OpenClaw | laufend | Debian konfiguriert | UNKNOWN | Steuerungs-/Agent-Dienst | nicht autorisiert |
| 107 | paperless-ngx | laufend | Debian konfiguriert | UNKNOWN | Daten-/Anwendungsdienst | nicht autorisiert |
| 108 | zigbee2mqtt-womo | laufend | Debian konfiguriert | UNKNOWN | Hausautomatisierung | nicht autorisiert |
| 109 | mqtt | laufend | Debian konfiguriert | UNKNOWN | Infrastruktur-/Broker-Dienst | nicht autorisiert |
| 110 | npm | laufend | Debian konfiguriert | UNKNOWN | Reverse-Proxy-Dienst | nicht autorisiert |
| 111 | pve-touch-dashboard | laufend | Debian konfiguriert | UNKNOWN | Bedien-/Dashboard-Dienst | nicht autorisiert |
| 112 | stellantis-oauth-worker | gestoppt | Debian konfiguriert | UNKNOWN | gestoppt; nicht starten | nicht geprüft |

Damit ist derzeit kein Container als produktiv geeigneter Simulationskandidat
nachgewiesen. Die neun laufenden Debian-konfigurierten LXCs sind technische
Kandidaten für eine spätere Einzelprüfung, aber nicht automatisch autorisiert.

## Geplante Freigabematrix

Die geplante Allowlist bleibt leer, bis je CTID die offenen Nachweise und die
Risikoabnahme vorliegen. Es gibt keine Wildcard und keine automatisch aus dem
Inventar erzeugte Allowlist.

Für jeden später freizugebenden laufenden Kandidaten gilt derselbe Vertrag:

- root-owned Eintrag `[containers."<CTID>"]` mit `authorized=true`;
- nachgewiesenes `os_name` Debian oder Ubuntu, konkrete `os_version` und
  `package_manager=apt`;
- Helper-Dienst, Socket und Allowlist root-owned und separat verifiziert;
- `read`: festes `/usr/bin/apt list --upgradable`;
- `simulate`: festes `apt-get --simulate --no-remove ... upgrade`;
- kein `apt update`, keine Installation/Entfernung, keine freie Shell und kein
  VM-Transport;
- Negativtests für nicht allowlistete IDs, gestoppte CTs, falsche IDs,
  ungültige Operationen, Timeout, Ausgabelimit und parallele Doppelanfragen;
- Abnahme: frischer passiver Nachweis, erfolgreicher Read- und Simulationspfad,
  keine Paketmutation, kein automatischer Start und unverändert deaktivierter
  Installationspfad.

Bis zur Erfüllung dieser Gates lautet die geplante Allowlist: **keine aktiven
Einträge**. CT 112 bleibt auch nach einer möglichen OS-Prüfung ausgeschlossen,
solange er gestoppt ist.

## Helper-Sicherheitsbefund

Der Repository-Helper ist für eine isolierte spätere Aktivierung vorbereitet:
numerische CTIDs, root-owned Allowlist, Peer-UID-Prüfung, feste Operationen
`read`/`simulate`, feste Argumentlisten, 10-Sekunden-Timeout, 256-KiB-
Ausgabelimit, Concurrency-Schutz auf Agent-Seite und keine Start-/Installations-
oder `apt update`-Pfade. Produktiv fehlen derzeit absichtlich Helper-Binary,
Socket und Allowlist.

## Spätere Aktivierungsschritte

1. Pro geeigneter laufender CTID die OS-/Versions-/APT-Nachweise passiv
   dokumentieren und das Betriebsrisiko bestätigen.
2. Je Ziel einen isolierten Mock-/Helper-Test einschließlich Negativtests
   bestehen lassen.
3. Eine konkrete, von Hand geprüfte Allowlist mit genau diesen CTIDs erstellen.
4. Helper-Datei, Dienst, Socket, Besitzer, Modi und Hash verifizieren.
5. Erst nach separater Freigabe Helper und Allowlist produktiv aktivieren.
6. Read-only-Nachkontrolle durchführen und danach je Ziel die Simulation
   separat freigeben; keine Sammelfreigabe aus der Inventur ableiten.

## Ergebnis

Die Entwicklungs- und Dokumentationsvorbereitung ist zulässig. Die
produktive Gesamtaktivierung ist **NO-GO**, solange OS/APT für die neun
laufenden Kandidaten nicht nachgewiesen und Helper/Allowlist nicht in einem
separat freigegebenen Sicherheitsfenster geprüft sind.
