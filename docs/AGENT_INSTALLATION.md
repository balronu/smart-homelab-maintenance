# Agent-Installation

Dieses Dokument beschreibt den späteren, kontrollierten Installationsweg des
Smart-Homelab-Maintenance-Agenten auf Proxmox. Der Agent ist in der aktuellen
Phase noch nicht für einen produktiven Start freigegeben. Die lesende
Proxmox-API-Anbindung und TLS-Server-Runtime sind implementiert; die isolierte
HA-Laufzeitabnahme und Infrastrukturfreigabe müssen noch erfolgen.

## 1. Voraussetzungen

- Proxmox VE mit systemd, Python 3 und `python3-venv`
- root-Zugriff für die Installation
- geprüfter Git-Commit des Projekts; keine unbestätigten Downloads
- private DNS-Adresse unter `.home.arpa`, `.lan` oder `.local`
- Zertifikat einer CA, der Home Assistant und der Agent vertrauen
- passender privater Schlüssel; Zertifikat und Schlüssel müssen zusammengehören
- freier interner Port ab 1024; Port 8128 des alten Dienstes wird nicht verwendet
- bestätigte Netzwerk-Allowlist; der Installer öffnet keine Firewallports
- private Proxmox-API-URL, Knotename und Proxmox-Credential mit Modus 600
- CA-Datei, die das Proxmox-Zertifikat validiert

Der Agent benötigt einen eigenen Servicebenutzer und verwendet ausschließlich
sein eigenes Installations-, Konfigurations- und Zustandsverzeichnis. Dateien
des bestehenden `homelab-wartung`-Systems werden nicht gelesen.

## 2. Quelle und Integrität

Der Installer lädt nichts aus dem Internet. Die Quelle wird von einem
Operator bereitgestellt und über einen exakten Commit geprüft:

```bash
git clone https://github.com/balronu/smart-homelab-maintenance.git /tmp/smart-homelab-maintenance
cd /tmp/smart-homelab-maintenance
git checkout --detach <GEPRUEFTER_COMMIT>
git rev-parse HEAD
git diff --quiet
```

Die ausgegebene SHA muss mit dem freigegebenen Wert verglichen werden. Der
Installer prüft zusätzlich, dass die Quelle die Agent-, HA- und systemd-Dateien
enthält und keine uncommitteten Änderungen besitzt.

## 3. TLS und DNS vorbereiten

Der private DNS-Name muss auf den freigegebenen internen TLS-Proxy oder Tunnel
zeigen. Der Agent selbst bindet lokal; eine externe Erreichbarkeit darf nur über
einen separat geprüften, authentifizierten TLS-Weg erfolgen.

```bash
openssl x509 -in /etc/ssl/private/smart-homelab-agent.crt -noout -subject -issuer -dates
openssl x509 -in /etc/ssl/private/smart-homelab-agent.crt -noout -checkend 86400
```

Selbstsignierte Zertifikate ohne vertrauenswürdige CA, deaktivierte
Zertifikatsprüfung und Klartext-HTTP sind nicht zulässig. Der Installer prüft
Ablaufdatum und die Zuordnung von Zertifikat und Schlüssel.

## 4. Vorprüfung

Die Vorprüfung verändert nichts:

```bash
sudo scripts/install-agent.sh \
  --source-dir /tmp/smart-homelab-maintenance \
  --expected-commit <GEPRUEFTER_COMMIT> \
  --cert /etc/ssl/private/smart-homelab-agent.crt \
  --key /etc/ssl/private/smart-homelab-agent.key \
  --agent-host agent.home.arpa \
  --port 48128 \
  --proxmox-url https://pve.home.arpa:8006/api2/json \
  --proxmox-node pve \
  --proxmox-ca /etc/ssl/certs/proxmox-ca.crt \
  --proxmox-token-file /etc/smart-homelab-maintenance/proxmox-api-token
```

Die Prüfung stoppt bei fehlendem Proxmox-/Python-Voraussetzungen, ungültigem
TLS, öffentlichem Hostnamen, falschem Commit oder unvollständiger Quelle.

## 5. Installation

Erst nach separater Infrastrukturfreigabe darf der Apply-Schalter verwendet
werden:

```bash
sudo scripts/install-agent.sh \
  --source-dir /tmp/smart-homelab-maintenance \
  --expected-commit <GEPRUEFTER_COMMIT> \
  --cert /etc/ssl/private/smart-homelab-agent.crt \
  --key /etc/ssl/private/smart-homelab-agent.key \
  --agent-host agent.home.arpa \
  --port 48128 \
  --proxmox-url https://pve.home.arpa:8006/api2/json \
  --proxmox-node pve \
  --proxmox-ca /etc/ssl/certs/proxmox-ca.crt \
  --proxmox-token-file /etc/smart-homelab-maintenance/proxmox-api-token \
  --apply
```

Dabei werden ausschließlich eigene Pfade unter `/opt/smart-homelab-maintenance`,
`/etc/smart-homelab-maintenance` und `/var/lib/smart-homelab-maintenance`
angelegt. Ein Agent-API-Credential wird geschützt erzeugt, falls noch keines
existiert. Das Proxmox-Credential muss bereitgestellt werden und wird nur
geschützt kopiert. Tokenwerte werden niemals ausgegeben.

Der Installer führt kein `enable` und kein `start` aus. Die Unit wird nur
abgelegt und systemd neu eingelesen. Für einen späteren Start werden beide
systemd-Credentials geladen; die Runtime bietet ausschließlich lesende
Endpunkte.

## 6. Verbindung mit Home Assistant

Nach einer separaten TLS-Proxy-/Tunnel-Abnahme verwendet Home Assistant die
private HTTPS-Adresse des Proxywegs, nicht `127.0.0.1` der HAOS-VM und nicht
den alten Port 8128. Der Token wird im Config Flow geschützt eingetragen und
darf nicht in Logs oder Diagnosen erscheinen.

Vor dem Eintrag müssen folgende lesende Prüfungen erfolgreich sein:

```text
GET /api/v1/health
GET /api/v1/capabilities        (Bearer-Token)
GET /api/v1/containers           (Bearer-Token)
```

Es werden keine Update- oder Shell-Endpunkte angeboten.

## 7. Funktionstest

Die spätere Abnahme erfolgt zuerst mit Mock-Daten und anschließend in einer
isolierten HA-Testumgebung. Zu prüfen sind TLS-Hostname/CA, gültiges und
ungültiges Token, Timeouts, API-Version, Pagination, Cursor-Ereignisse,
dynamische Container/VMs und `execution_enabled=false`.

Ein Test gegen VM 104 oder produktive Container ist kein Ersatz für diese
Abnahme und benötigt eine eigene Freigabe.

## 8. Fehlerbehandlung

- **TLS-Fehler:** Zertifikatskette, SAN, Ablaufdatum und CA prüfen; keine
  Prüfung deaktivieren.
- **401/403:** Credential-Quelle prüfen; Token niemals in die Shell-History
  oder ein Log schreiben.
- **Timeout/Verbindung:** DNS, freigegebenen Proxyweg und Allowlist prüfen;
  keine beliebige URL freischalten.
- **Runtime nicht startbereit:** Installation nicht erzwingen; zuerst das
  Live-Backend und den isolierten HA-Laufzeittest abnehmen.
- **Aktiver Dienst beim Update/Uninstall:** Skripte brechen ohne Stop/Restart
  ab.

## 9. Updates

Updates werden niemals automatisch aktiviert. Quelle, Commit und TLS werden
erneut geprüft:

```bash
sudo scripts/update-agent.sh \
  --source-dir /tmp/smart-homelab-maintenance \
  --expected-commit <NEUER_GEPRUEFTER_COMMIT>
```

Erst nach Prüfung und bewusstem Apply:

```bash
sudo scripts/update-agent.sh \
  --source-dir /tmp/smart-homelab-maintenance \
  --expected-commit <NEUER_GEPRUEFTER_COMMIT> \
  --apply
```

Ein aktiver Dienst wird nicht automatisch gestoppt oder neugestartet.

## 10. Prüfung und Deinstallation

```bash
sudo scripts/check-agent.sh
sudo scripts/uninstall-agent.sh --confirm smart-homelab-maintenance
```

Die Deinstallation ist standardmäßig nur eine Vorprüfung. Mit `--apply` werden
nur Agent-Code, eigene Konfiguration und die eigene Unit entfernt. Das
Zustandsverzeichnis bleibt absichtlich erhalten; bestehende Proxmox-Dienste,
der alte Wartungsdienst und fremde Wartungsdaten werden nicht gelöscht.

```bash
sudo scripts/uninstall-agent.sh \
  --confirm smart-homelab-maintenance \
  --apply
```

## Aktueller Freigabestatus

Der dokumentierte Weg ist technisch vorbereitet, aber für eine kontrollierte
Installation derzeit **NO-GO**. Erforderlich sind die isolierte HA-2026.11-
Abnahme, private TLS-/DNS-/Netzwerkstrecke und eine gesonderte Freigabe für
Installations- und Starttest.
