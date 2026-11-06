# Phase 4.5 – Proxmox-Agent-Installer

**Projekt:** `balronu/smart-homelab-maintenance`
**Arbeitszweig:** `phase4-5-agent-installer`
**Ausgangsstand:** PR #2, Commit `924aa3e3872a66edaf446da7a0e8a0bc4719ff2f`

## 1. Implementierte Installationsfunktionen

Unter `scripts/` wurden folgende Werkzeuge ergänzt:

- `install-agent.sh`: Vorprüfung und expliziter Apply-Modus
- `update-agent.sh`: commit-geprüftes Update ohne automatischen Stop/Restart
- `check-agent.sh`: lokale Datei- und Unit-Prüfung
- `uninstall-agent.sh`: explizit bestätigte Entfernung nur eigener Dateien
- `agent-common.sh`: gemeinsame Validierungs- und Credential-Helfer

Der Installer:

- verlangt root, Python, `python3-venv`, systemd und Proxmox-Voraussetzungen
- akzeptiert nur einen exakt angegebenen, sauberen Git-Commit
- prüft private DNS-Suffixe und lehnt öffentliche Agent-Hosts ab
- prüft Ablauf, Lesbarkeit und Paarung von TLS-Zertifikat und Schlüssel
- verwendet eine eigene venv, einen eigenen Servicebenutzer und eigene Pfade
- erzeugt ein zufälliges Token mit Modus 600, ohne es auszugeben
- legt eine gehärtete systemd-Unit ab, führt aber kein `enable` oder `start` aus
- öffnet keine Ports und verändert keine DNS-/Firewall-Konfiguration

Die Installationspfade sind `/opt/smart-homelab-maintenance`,
`/etc/smart-homelab-maintenance` und `/var/lib/smart-homelab-maintenance`.
Das Zustandsverzeichnis wird bei der Deinstallation bewusst erhalten.

## 2. TLS- und Installationsdokumentation

Die vollständige, kopierbare Anleitung steht in
[`docs/AGENT_INSTALLATION.md`](AGENT_INSTALLATION.md). Sie beschreibt Quelle
und Integritätsprüfung, private DNS-/CA-Anforderungen, Dry-Run, Apply,
Home-Assistant-Verbindung, Fehlerfälle, Updates und Deinstallation.

Klartext-HTTP, deaktivierte Zertifikatsprüfung, selbstsignierte Zertifikate
ohne vertrauenswürdige CA und automatische Firewallfreigaben sind nicht
zulässig.

## 3. Isolierte Prüfungen

| Prüfung | Ergebnis |
|---|---|
| 27 Core-/Backend-Tests | **PASSED** |
| Python-Compilecheck | **PASSED** |
| Frontend-Card-State-Tests | **PASSED** |
| Shell-Syntax aller fünf Skripte | **PASSED** |
| Secret-/Live-Reference-Scan | **PASSED** |
| Shell-/Browser-Ausführungsscan | **PASSED** |
| Tatsächlicher Apply-Lauf | **NOT RUN** – würde systemd, Benutzer und `/opt`/`/etc` verändern |
| Tatsächlicher Update-/Deinstallationslauf | **NOT RUN** – produktive Mutation ausgeschlossen |
| HA-2026.11-Runtime lokal | **BLOCKED / NOT RUN** – lokale Fixtures fehlen |

Die Tests decken den nicht-mutierenden Pfad, ungültige Eingaben und die
statischen Sicherheitsgates ab. Ein Apply-Test benötigt eine eigene, isolierte
Proxmox-Test-VM oder einen vollständig virtualisierten systemd-Testroot und
wurde nicht durch Änderungen am Produktivhost ersetzt.

## 4. CI und PR

Die Änderungen sind für PR #2 vorgesehen. Remote-CI wird erst nach dem Push
dieses Feature-Branches erneut ausgeführt. Bis dahin ist der Remote-Status für
diesen Phase-4.5-Kandidaten **NOT RUN**; frühere CI-Läufe gehören zum
Phase-4.4-Stand und werden nicht übernommen.

## 5. Noch erforderliche Infrastrukturvoraussetzungen

Vor jedem Apply oder kontrollierten Installationstest fehlen weiterhin:

1. ein produktionsreifes Server-Startmodul mit Konfigurationsparser;
2. ein echtes, nur lesendes Proxmox-Backend;
3. private DNS-/TLS-/Proxy-Infrastruktur mit vertrauter CA;
4. isolierte HA-2026.11-Transport- und Registry-Abnahme;
5. ein separater, freigegebener Installationstest außerhalb von VM 104.

Die aktuelle systemd-Vorlage verweist deshalb weiterhin auf die noch nicht
freigegebene Live-Runtime. Ein Dienst darf nicht gestartet werden, nur weil die
Unit-Datei installiert wurde.

## 6. Entscheidung

**GO für Dokumentation, Dry-Run und lokale Skriptvorbereitung.**

**NO-GO für kontrollierten Installations- oder Produktivtest.** Der Apply-Weg
ist sicher begrenzt, aber Server-Runtime und Live-Proxmox-Backend sind noch
nicht vollständig abgenommen. Keine produktiven Dienste, HA VM 104, Proxmox-
Konfigurationen, DNS-/Firewallregeln, Backups, Snapshots oder bestehenden
Wartungssysteme wurden verändert.
