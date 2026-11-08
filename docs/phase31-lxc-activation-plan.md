# Phase 31: Gemeinsamer LXC-Aktivierungs- und Abnahmeplan

Dieses Dokument ist ein Prüf- und Freigabeplan. Es installiert keinen Helper,
schreibt keine Allowlist und führt keine Gast-Simulation aus. Der Plan gilt
für PR #54 auf dem geprüften Head `e9b3eb919c046e3589ec41c6f2ef2bff92007fe7`.

## Zielmatrix

Alle neun laufenden, nachgewiesenen Debian-/APT-Ziele werden berücksichtigt.
CT112 bleibt gestoppt und wird nicht aktiviert.

| CTID | Name | OS/APT | Risiko | geplanter Zugriff | Abbruchkriterium |
|---:|---|---|---|---|---|
| 101 | cloudflared | Debian 13 / apt 3.0.4 | Netzwerk-Edge | Helper read, dann simulate | Dienst-/Netzwerkfehler |
| 102 | zigbee2mqtt-haus | Debian 13 / apt 3.0.4 | Hausautomatisierung | Helper read, dann simulate | Geräte-/Dienstfehler |
| 103 | mariadb | Debian 13 / apt 3.0.4 | Datenbank, migrationssensitiv | Helper read, dann simulate | Datenbank-/Migrationsrisiko |
| 105 | OpenClaw | Debian 13 / apt 3.0.4 | Steuerungs-/Agent-Dienst | Helper read, dann simulate | Steuerungs-/Dienstfehler |
| 107 | paperless-ngx | Debian 13 / apt 3.0.4 | Daten-/Anwendungsdienst | Helper read, dann simulate | Daten-/Dienstfehler |
| 108 | zigbee2mqtt-womo | Debian 13 / apt 3.0.4 | Hausautomatisierung | Helper read, dann simulate | Geräte-/Dienstfehler |
| 109 | mqtt | Debian 13 / apt 3.0.4 | Infrastruktur-/Broker-Dienst | Helper read, dann simulate | Broker-/Dienstfehler |
| 110 | npm | Debian 12 / apt 2.6.2 | Reverse Proxy | Helper read, dann simulate | Proxy-/Dienstfehler |
| 111 | pve-touch-dashboard | Debian 12 / apt 2.6.2 | Bedien-/Dashboard-Dienst | Helper read, dann simulate | Dashboard-/Dienstfehler |

Die Matrix ist keine Sammelautorisierung. Die geplante Allowlist enthält nur
diese exakten numerischen IDs und bleibt bis zur separaten Freigabe inaktiv.

## Pro-Ziel-Abnahme

Für jede CTID, in der angegebenen Reihenfolge:

1. Root-owned Helper, Unix-Socket und Allowlist sowie Hash/Modus prüfen.
2. Allowlist-Eintrag und laufenden Status ausschließlich über den Helper prüfen.
3. Einen erfolgreichen festen `read`-Aufruf nachweisen.
4. Einen festen `simulate`-Aufruf nachweisen; keine Paketmutation und kein
   `apt update`.
5. API muss `supported=true`, die feste Simulationsmethode und ein Ergebnis
   melden; das Dashboard zeigt Status, Anzahl und Sicherheitsprüfung.
6. Bei jedem Fehler keine weitere CTID aktivieren; Ursache und Zustand sichern.

Negativfälle je Ziel und vor einer gemeinsamen Aktivierung:

- nicht allowlistete numerische CTID: `container_not_allowed`;
- ungültige/nichtnumerische CTID oder zusätzliche Request-Felder:
  `invalid_container`/`invalid_request`;
- Operation außerhalb `read`/`simulate`: `operation_not_allowed`;
- gestoppter Container: `not_running`, ohne Startversuch;
- fehlender/falsch berechtigter Helper, Socket oder Allowlist: sicherer Fehler;
- Timeout, Ausgabelimit und parallele Doppelanfrage: Abbruch ohne Mutation;
- VM-ID: serverseitig abgewiesen und niemals an `pct exec` weitergeleitet;
- Installations-/Entfernungs-/`apt update`-Anfrage: nicht im Protokoll zulässig.

Erwarteter Fehlerstatus bleibt unterscheidbar: `unauthorized`,
`helper-unavailable`, `not_checked`/`stopped` und technische Fehler dürfen
nicht zu einem aktivierten Button zusammenfallen.

## Sicherheitsvertrag

- Helper läuft root-owned als separater Dienst; Socket ist Unix-only und
  peer-UID-geschützt.
- Allowlist ist root-owned, nicht durch Gruppe/Andere schreibbar und wird je
  Request neu validiert.
- Nur numerische CTIDs, feste Argumentlisten und `read`/`simulate`.
- Kein freier Shell-Runner, kein VM-Transport, kein automatischer Start.
- Kein `apt update`, keine Installation, Entfernung oder Paketmutation.
- Timeout, Ausgabelimit und Concurrency-Schutz sind Pflicht.
- Der allgemeine Installationspfad bleibt dauerhaft deaktiviert.

## Gemeinsames Aktivierungsfenster

Voraussetzungen vor produktiven Änderungen:

1. Neue Freigabe für Helper-/Socket-Installation und genau diese Allowlist.
2. Statischer Review von Helper, Service, Besitzern, Modi, Hash und Unit.
3. Isolierte Negativtests grün.
4. Read-/Simulations-Abnahme je CT101, 102, 103, 105, 107, 108, 109, 110,
   111; CT112 bleibt aus.
5. Nach jedem Ziel passive API-/Dashboard-Nachkontrolle.
6. Bei Fehler sofort Stopp aller weiteren Ziele; keine automatische Reparatur
   und keine Wiederholung ohne neue Entscheidung.
7. Abschließende Prüfung, dass VMs, Installationspfad, Firewall, Paketquellen,
   Gäste und bestehende Stagings unverändert sind.

## Stable-Entscheidung

Entwicklungs- und Dokumentationsstand: **GO**. Produktives
Aktivierungsfenster: **NO-GO**, bis die obigen Voraussetzungen separat
freigegeben und je Ziel nachgewiesen sind.
