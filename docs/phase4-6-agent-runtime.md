# Phase 4.6 – Agent-Runtime und Proxmox-Client

## Ergebnis

Die Softwareblocker für einen isolierten, lesenden Agent-Test wurden im
Feature-Branch `phase4-6-agent-runtime` bearbeitet. Es wurden keine
produktiven Dienste gestartet und keine Proxmox- oder HA-Systeme verändert.

## Implementierung

- `ProxmoxApiClient` verwendet ausschließlich HTTPS-GETs gegen die versionierte
  Proxmox-JSON-API.
- TLS-Zertifikats- und Hostname-Prüfung sind aktiv; Antworten sind begrenzt.
- 401/403, TLS-Fehler, Timeouts und ungültige JSON-Antworten werden in
  strukturierte, geheimnisfreie Fehler übersetzt.
- Hoststatus, LXC- und VM-Status sowie belastbare Ressourcenwerte werden in die
  bestehende Discovery-Abstraktion überführt. Betriebssysteme,
  Paketmanager und Anwendungsversionen bleiben unbekannt, wenn die API sie
  nicht zuverlässig liefert.
- `server.py` lädt TOML-Konfiguration und zwei getrennte systemd-Credentials,
  baut die SQLite-Jobpersistenz und startet ausschließlich den vorhandenen
  read-only API-Routenraum.
- systemd-Vorlage und Installer wurden um das Proxmox-CA-/Credential-Modell
  ergänzt. `enable`, `start`, Updates und Shell-Kommandos bleiben gesperrt.

## Tests

| Prüfung | Ergebnis |
|---|---|
| Python-Compile | PASSED |
| Offline-Core-Regression | PASSED – 30 Tests |
| Shell-Syntax Installer | PASSED |
| Produktiver Proxmox-Zugriff | NOT RUN – ausdrücklich ausgeschlossen |
| HA-2026.11-Laufzeit in GitHub Actions | PASSED |
| Hassfest/HACS/Browsermatrix | PASSED |

Die Clienttests verwenden ausschließlich Fake-HTTP-Antworten und prüfen
GET-only, Bearer-Header, Größenbegrenzung, private URL-Gates und strukturierte
Authentifizierungsfehler.

Der geprüfte PR-Head ist `dfe731483fbf1d85ac666070c0f64e3aa7e4b9d7`.
Die beiden verifizierten Actions-Läufe sind
[42222074564](https://github.com/balronu/smart-homelab-maintenance/actions/runs/42222074564)
und
[42222086490](https://github.com/balronu/smart-homelab-maintenance/actions/runs/42222086490);
alle acht Jobs waren erfolgreich.

## Offene Infrastrukturvoraussetzungen

- private DNS-/Routing-/Firewall-Freigabe zwischen HA und Agent;
- vertrauenswürdige CA und Zertifikat-SANs für Agent und Proxmox;
- isolierte HA-2026.11-Runtimeabnahme und kontrollierter Installationsstart;
- separat freigegebene Proxmox-API-Leseberechtigung.

## Freigabestatus

**NO-GO für produktive Installation.** Der Softwarestand ist für CI und einen
isolierten Mock-/TLS-Test vorbereitet. Ein kontrollierter Installationstest
bleibt bis zur erfolgreichen Remote-CI, Infrastrukturprüfung und ausdrücklichen
Freigabe ausgeschlossen.
