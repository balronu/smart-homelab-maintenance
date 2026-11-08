# Phase 29: LXC-Eignungs- und Aktivierungsmatrix

Stand: 2026-11-08. Diese Matrix ist eine passive Bestandsaufnahme und keine
Produktivfreigabe. Es wurden keine Gastbefehle, `pct exec`, Starts,
Allowlist-Änderungen oder Helper-Aktivierungen durchgeführt.

## Passive Befunde

Proxmox meldet für alle zehn Container `ostype=debian`. Die neun laufenden
Container wurden danach im ausdrücklich freigegebenen, sequenziellen
Lesepfad geprüft. CT101–109 melden Debian 13 (trixie), `apt 3.0.4` und
`dpkg-query 1.22.22`; CT110–111 melden Debian 12 (bookworm), `apt 2.6.2`
und `dpkg-query 1.21.23`. Es wurden keine Paketlisten aktualisiert und keine
Pakete verändert.

| CTID | Name | Zustand | Proxmox-OS | Version/APT | Risiko-/Besonderheit | Aktueller Status |
|---:|---|---|---|---|---|---|
| 101 | cloudflared | laufend | Debian 13 (trixie) | apt 3.0.4, dpkg-query 1.22.22 | Netzwerk-/Edge-Dienst | nicht autorisiert |
| 102 | zigbee2mqtt-haus | laufend | Debian 13 (trixie) | apt 3.0.4, dpkg-query 1.22.22 | Hausautomatisierung | nicht autorisiert |
| 103 | mariadb | laufend | Debian 13 (trixie) | apt 3.0.4, dpkg-query 1.22.22 | Datenbank, migrationssensitiv | nicht autorisiert |
| 105 | OpenClaw | laufend | Debian 13 (trixie) | apt 3.0.4, dpkg-query 1.22.22 | Steuerungs-/Agent-Dienst | nicht autorisiert |
| 107 | paperless-ngx | laufend | Debian 13 (trixie) | apt 3.0.4, dpkg-query 1.22.22 | Daten-/Anwendungsdienst | nicht autorisiert |
| 108 | zigbee2mqtt-womo | laufend | Debian 13 (trixie) | apt 3.0.4, dpkg-query 1.22.22 | Hausautomatisierung | nicht autorisiert |
| 109 | mqtt | laufend | Debian 13 (trixie) | apt 3.0.4, dpkg-query 1.22.22 | Infrastruktur-/Broker-Dienst | nicht autorisiert |
| 110 | npm | laufend | Debian 12 (bookworm) | apt 2.6.2, dpkg-query 1.21.23 | Reverse-Proxy-Dienst | nicht autorisiert |
| 111 | pve-touch-dashboard | laufend | Debian 12 (bookworm) | apt 2.6.2, dpkg-query 1.21.23 | Bedien-/Dashboard-Dienst | nicht autorisiert |
| 112 | stellantis-oauth-worker | gestoppt | Debian konfiguriert | nicht geprüft | gestoppt; nicht starten | nicht geprüft |

Damit sind alle neun laufenden Container technisch als Debian-/APT-Kandidaten
nachgewiesen. Das ist noch keine Simulationsfreigabe: alle bleiben bis zur
separaten Risikoabnahme und Allowlist-Aktivierung `unauthorized`.

## Geplante Freigabematrix

Die geplante, noch nicht aktive Allowlist umfasst nach erfolgreicher
Einzel-Risikoabnahme exakt die laufenden CTIDs 101, 102, 103, 105, 107, 108,
109, 110 und 111. Es gibt keine Wildcard und keine automatisch aktivierte
Allowlist.

Vorgesehene Einträge (Plan, nicht produktive Konfiguration):

```text
101 Debian 13 apt
102 Debian 13 apt
103 Debian 13 apt
105 Debian 13 apt
107 Debian 13 apt
108 Debian 13 apt
109 Debian 13 apt
110 Debian 12 apt
111 Debian 12 apt
```

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

Die OS-/APT-Nachweise für alle neun laufenden Kandidaten sind PASS. Die
Entwicklungs- und Dokumentationsvorbereitung ist abgeschlossen; die
produktive Gesamtaktivierung bleibt **NO-GO**, solange Helper/Allowlist nicht
in einem separat freigegebenen Sicherheitsfenster installiert, geprüft und
je CTID abgenommen sind.
