# Phase 4.3 – Vorbereitung des Proxmox-Agenten

**Projekt:** Smart Homelab Maintenance
**Arbeitsstand:** lokaler Vorbereitungsbranch `phase4-3-agent-preparation`
**Bewertung:** lokale Vorbereitung GO; spätere Agent-Installation NO-GO

## 1. Agent-Implementierungsstatus

Der Repository-Stand enthält einen offline testbaren, authentifizierten
In-Process-Agenten. Die API stellt ausschließlich lesende Endpunkte unter
`/api/v1/` bereit:

- `health` (minimaler, unauthentifizierter Healthcheck)
- `capabilities`, `containers`, `apps/{app_id}`
- `jobs`, `jobs/{job_id}`, `jobs/{job_id}/events`

Die übrigen Endpunkte verlangen Bearer-Authentifizierung. Antworten sind
versioniert, größenbegrenzt und strukturierte Fehler enthalten keine
Geheimnisse. Container- und Anwendungserkennung sowie persistente Jobs und
Ereignisse sind im Offline-Kern vorhanden. Ein produktiver HTTP-Listener und
ein live angebundener Proxmox-Backend sind in diesem Stand **nicht** enthalten.

Die Ausführungsgrenze bleibt global deaktiviert: `execution_enabled=false`;
die Adapter melden keine ausführbare Updateaktion. Ein beendeter Prozess kann
damit nicht als erfolgreiches Update gelten.

## 2. Vorgesehene Betriebsstruktur

Unter `deploy/systemd/` liegen ausschließlich nicht installierte Beispiele:

- eigener Systembenutzer und eigene Gruppe `smart-homelab-maintenance`
- eigener interner Beispielport `48128` (nicht der bestehende Port 8128)
- eigener Zustandsbereich `/var/lib/smart-homelab-maintenance`
- `systemd LoadCredential` für das API-Token statt Token in der TOML-Datei
- `NoNewPrivileges`, schreibgeschütztes System, private Geräte und
  eingeschränkte Fähigkeiten

Die Unit verweist bewusst auf ein noch nicht vorhandenes `server`-Modul und
ist deshalb nicht startfähig. Sie wurde weder installiert noch aktiviert. Der
neue Agent liest keine Dateien des bestehenden `homelab-wartung`-Dienstes.

## 3. HTTPS-Konzept

Der HTTP-Transport akzeptiert ausschließlich private HTTPS-Ziele. Zulässig
sind kontrollierte private DNS-Suffixe (`.home.arpa`, `.lan`, `.local`) sowie
private, Loopback- und Link-Local-Adressen. Öffentliche Ziele, URLs mit
Benutzerdaten, Query- oder Fragmentanteil und ungeschütztes HTTP werden
abgelehnt.

TLS verwendet den System-Truststore oder eine explizit übergebene CA-Datei,
aktivierte Zertifikatsprüfung und Hostname-Prüfung. Zertifikatsfehler werden
als strukturierter `tls_error` gemeldet; Authentifizierungsfehler als
`authentication`. Tokens werden nur als Bearer-Header übertragen und nicht
in Fehlermeldungen oder Diagnosen ausgegeben.

Vorgesehen ist ein lokal gebundener Agent hinter einem separat betriebenen,
intern erreichbaren TLS-Reverse-Proxy oder einem abgesicherten privaten
Tunnel. DNS-, Firewall- und Proxy-Änderungen sind in dieser Phase nicht
erfolgt. Selbstsignierte Zertifikate ohne vertrauenswürdige CA sind nicht
zulässig.

## 4. Änderungen am Home-Assistant-Config-Flow

Der Config Flow validiert und normalisiert nun private HTTPS-Agent-URLs,
führt den Verbindungstest über den gemeinsamen Transport aus und unterscheidet
ungültige URL, API-Versionskonflikt, Authentifizierungs- und TLS-Fehler.
Die bisherige harte Localhost-HTTP-Beschränkung wurde entfernt; eine pauschale
Freigabe beliebiger Netzwerkziele gibt es nicht.

Der aktuelle Config-Entry verwendet weiterhin das bestehende HA-
Credential-Feld für den Token. Die SecretRef-basierte Ablage ist für die
spätere systemd-Betriebsstruktur vorbereitet; eine gesonderte HA-
SecretRef-Migration muss vor einem produktiven Netzwerkbetrieb entschieden
und getestet werden.

## 5. Bestandsaufnahme der vorhandenen Infrastruktur

Die lesende Prüfung aus Phase 4.2 ergab:

- Ein neuer Smart-Homelab-Agent ist auf dem geprüften Proxmox-System nicht
  installiert und kein entsprechender Dienst läuft.
- Der vorhandene Dienst `homelab-wartung-http.service` ist ein getrenntes
  Altsystem auf Port 8128 mit einer anderen API (`/api/...` statt
  `/api/v1/...`). Er bleibt unverändert.
- Der Pfad von HA VM 104 zum bestehenden Dienst war lesend erreichbar; dies
  beweist weder Agent-Kompatibilität noch TLS-Betriebsbereitschaft.
- Es wurden keine Ports, Firewallregeln, DNS-Einträge, Dienste oder HA-
  Konfigurationen verändert.

## 6. Offline-Validierung

| Prüfung | Ergebnis |
|---|---|
| Core-Regressionstests | **PASSED** – 24 Tests |
| Python-Compilecheck | **PASSED** |
| JSON-/Manifest-nahe Strukturprüfung | **PASSED** |
| Frontend-Card-State-Tests | **PASSED** |
| Git-Diff-Whitespace-Prüfung | **PASSED** |
| Echte HA-Laufzeit-Fixtures | **BLOCKED / NOT RUN** – lokale Umgebung enthält weder `homeassistant` noch `pytest-homeassistant-custom-component` |
| Live-Proxmox-Agent | **NOT RUN** – in dieser Phase ausdrücklich ausgeschlossen |
| HTTPS-End-to-End mit produktivem Agenten | **NOT RUN** – kein Agent/Listener vorhanden |

Die HTTP-Transporttests verwenden ausschließlich Mock-Aufrufe und prüfen
Bearer-Header, Hostname-/Zertifikatsprüfung, TLS-Fehler, URL-Sperren und
Größen-/Timeoutpfade. Für diesen lokalen Branch wurde noch kein neuer
GitHub-Actions-Lauf gestartet; historische CI-Ergebnisse werden nicht als
Ergebnis dieses Stands gewertet.

## 7. Noch erforderliche Infrastrukturfreigaben

Vor einer Installation müssen separat freigegeben und umgesetzt werden:

1. Festlegung des Agent-Hosts und des internen Bind-/Proxy-Designs.
2. Installation des noch fehlenden Servermoduls und eines echten, nur lesenden
   Proxmox-Discovery-Backends.
3. Eigenes Servicekonto, Zustandsverzeichnis und restriktive Dateirechte.
4. Private DNS-Adresse sowie Zertifikat einer von HA vertrauten CA.
5. Netzwerk-/Firewall-Allowlist ausschließlich für den vorgesehenen HA-Client.
6. Tokenbereitstellung über eine geschützte SecretRef bzw. Credential-Datei.
7. Isolierte HA-2026.11-Laufzeitprüfung gegen diesen HTTPS-Agenten.
8. Nachweis, dass Discovery, Jobs, Cursor-Ereignisse und Fehlerzustände ohne
   Updateausführung funktionieren.

## 8. Entscheidung

**GO für die lokale technische Vorbereitung.** Die Transport- und
Deployment-Grundlagen sind offline testbar und die Updateausführung bleibt
deaktiviert.

**NO-GO für eine Agent-Installation oder einen produktiven Netzwerkbetrieb.**
Es fehlen noch ein Servermodul, ein echtes Proxmox-Backend, vertrauenswürdiges
TLS/DNS, die Client-Allowlist, geschützte Credential-Bereitstellung und die
isolierte HA-Laufzeitvalidierung. Diese Punkte müssen vor jeder Installation
und vor jeder produktiven Verbindung abgeschlossen werden.

## 9. Unveränderte Systeme

Während dieser Phase wurden keine Dienste installiert oder gestartet, keine
Neustarts, Updates, Backups, Snapshots, DNS-/Firewall-/Proxy-Änderungen und
keine Änderungen an HA VM 104, Proxmox oder dem bestehenden Wartungssystem
durchgeführt.
