# Phase 4.4 – Agent-Server und Proxmox-Backend

**Projekt:** `balronu/smart-homelab-maintenance`
**Branch:** `phase4-4-agent-backend`
**Status:** Implementierung und isolierte CI abgeschlossen; isolierte Installation **NO-GO**

## 1. Implementierte API-Endpunkte

Das neue Modul `agent/smart_homelab_maintenance/server.py` stellt einen
stdlib-basierten HTTPS-Server für die vorhandene `ApiApplication` bereit.
Der Server wird nicht automatisch gestartet und ist nicht installiert.

| Methode | Endpunkt | Authentifizierung |
|---|---|---|
| GET | `/api/v1/health` | minimaler Healthcheck ohne Token |
| GET | `/api/v1/host` | Bearer-Token |
| GET | `/api/v1/capabilities` | Bearer-Token |
| GET | `/api/v1/containers` | Bearer-Token, Pagination |
| GET | `/api/v1/virtual-machines` | Bearer-Token, Pagination |
| GET | `/api/v1/apps/{app_id}` | Bearer-Token |
| GET | `/api/v1/jobs` | Bearer-Token, Pagination |
| GET | `/api/v1/jobs/{job_id}` | Bearer-Token |
| GET | `/api/v1/jobs/{job_id}/events` | Bearer-Token, Cursor |

POST-Anfragen und Update-Endpunkte werden abgelehnt. Antworten sind
versioniert, größenbegrenzt und enthalten strukturierte Fehler. Abgebrochene
Verbindungen werden behandelt, ohne Authentifizierungsdaten zu protokollieren.

## 2. Proxmox-Discovery

`agent/smart_homelab_maintenance/proxmox_backend.py` enthält einen strikt
lesenden, injizierbaren `ProxmoxReadClient`-Vertrag und die Übersetzung in die
Discovery-Datenmodelle:

- Proxmox-Hoststatus, Release und Kernel
- dynamische LXC-Erkennung mit VMID, Name, Status, OS und Ressourcenfeldern
- virtuelle Maschinen mit VMID, Name, Status und unbekannten OS-Feldern
- Anwendungserkennung aus den gelieferten Inventardaten
- unbekannte Versionen bleiben `None` beziehungsweise `unknown`

Der Backend-Adapter führt keine Shell-Kommandos aus und akzeptiert keine
Befehle aus API-Parametern. `FixtureProxmoxClient` dient ausschließlich den
Offline-Tests. Ein produktiver Proxmox-Client, seine Authentifizierung und
seine Berechtigungen sind bewusst noch nicht implementiert.

## 3. Sicherheitsmaßnahmen

- TLS ist für den Server zwingend; Zertifikat und Schlüssel müssen explizit
  vorhanden sein, Mindestversion TLS 1.2.
- Unbeschränkte Bind-Adressen (`0.0.0.0`, `::`) werden abgelehnt; Standard ist
  Loopback auf einem unprivilegierten internen Port.
- Bearer-Token wird über eine systemd-Credential-Datei geladen, nicht aus der
  Konfigurationsdatei und nicht aus API-Eingaben.
- `NoNewPrivileges`, private Geräte, schreibgeschütztes System und leere
  Capability-Bounding-Set sind in der nicht installierten Unit-Vorlage
  vorgesehen.
- Updateausführung bleibt unabhängig vom Server dauerhaft deaktiviert.
- Es gibt keine freie Shell- oder Wartungsaktion.
- Der bestehende `homelab-wartung`-Dienst und Port 8128 bleiben unberührt.

## 4. Persistenz und Jobs

Die vorhandene SQLite-Jobverwaltung wird unverändert verwendet. Sie bietet
persistente Zustände, Neustart-Recovery zu `manual_recovery_required`,
Idempotency, gegenseitige Ziel-Sperren, begrenzte Logs und Cursor-Ereignisse.
Der neue Server reicht diese Daten nur lesend weiter. Es wird kein neuer
Wartungsjob über HTTP gestartet.

## 5. Tests

| Prüfung | Ergebnis |
|---|---|
| Core- und Backend-Regression | **PASSED** – 27 Tests |
| HTTPS-/Transport-Sicherheitsprüfungen | **PASSED** – Mock-Transport und TLS-Gates |
| Proxmox-Fixture mit LXC und VM | **PASSED** |
| API-Auth, Pagination, Cursor und Antwortgrenzen | **PASSED** |
| Update-Sperre | **PASSED** |
| Python-Compilecheck | **PASSED** |
| JSON-/Manifest-Prüfung | **PASSED** |
| Frontend-Card-State-Tests | **PASSED** |
| `git diff --check` | **PASSED** |
| HA-2026.11-Laufzeittests lokal | **BLOCKED / NOT RUN** – HA- und pytest-Fixtures fehlen lokal |
| Produktiver Proxmox-Test | **NOT RUN** – ausdrücklich ausgeschlossen |
| Echte HTTPS-End-to-End-Kette mit installiertem Agenten | **NOT RUN** – kein produktiver Listener vorhanden |

Der PR [#2](https://github.com/balronu/smart-homelab-maintenance/pull/2) ist
offen und zeigt auf den geprüften Commit
`5c4014e52d67f6d0f387f1a97ee5869ded0e6f83`. Der terminale Pull-Request-Lauf
[`42217832902`](https://github.com/balronu/smart-homelab-maintenance/actions/runs/42217832902)
ist vollständig erfolgreich. Der parallele Push-Lauf
[`42217822601`](https://github.com/balronu/smart-homelab-maintenance/actions/runs/42217822601)
ist ebenfalls erfolgreich. Beide Läufe enthalten Python-Regression, API-
Vertrag, HA-Runtime, HA-Runtime-Tests, Hassfest, HACS, Browser und Security.
Die vorherigen Läufe auf dem Zwischenstand `7e395f2` waren wegen eines zu
breiten statischen Security-Patterns fehlgeschlagen und werden nicht als
Ergebnis des finalen Kandidaten gewertet.

## 6. Offene Infrastrukturvoraussetzungen

Vor einer isolierten Installation sind erforderlich:

1. Ein produktionsreifes Server-Startmodul und ein geprüfter Proxmox-
   REST-/API-Client mit minimalen Leserechten.
2. Eigenes Servicekonto, Zustandsverzeichnis und geschützte Credential-Datei.
3. Private DNS-Adresse, von HA vertraute CA und TLS-Client-/Server-Konzept.
4. Firewall-/Proxy-Allowlist nur für den vorgesehenen HA-Client.
5. Isolierte HA-2026.11-Laufzeittests einschließlich echter Config-/Entity-
   Registry und vollständiger Transportkette.
6. Read-back der Agent-API und Nachweis, dass keine Updateaktion erreichbar
   oder aktivierbar ist.

## 7. Entscheidung

**GO für den lokalen Entwicklungsstand und die isolierte CI-Prüfung.**

**NO-GO für Installation oder produktiven Betrieb.** Der Servercode ist
vorbereitet, aber der Live-Listener, das Proxmox-Backend, die Infrastruktur-
Freigaben und die HA-Laufzeitvalidierung fehlen noch. Eine erfolgreiche lokale
Python-Suite allein ist kein Installations- oder Beta-Gate.

Es wurden keine Dienste installiert oder gestartet, keine HA-/Proxmox-
Konfiguration, Firewall, DNS, Backups, Snapshots oder bestehenden
Wartungssysteme verändert.
