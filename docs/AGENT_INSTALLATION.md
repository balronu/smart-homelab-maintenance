# Agent-Installation

Dieses Dokument beschreibt den kontrollierten Installationsweg des
Smart-Homelab-Maintenance-Agenten auf Proxmox. Es ist eine Stable-
Vorbereitungsanleitung, keine Installationsfreigabe. Die aktuelle Anwendung
bleibt read-only und der Installationspfad serverseitig deaktiviert; jede
produktive Installation, jedes Upgrade und jeder Dienstneustart benötigen
eine eigene Freigabe.

Die zugehörige Abnahme ist in
[`docs/STABLE_ACCEPTANCE.md`](STABLE_ACCEPTANCE.md) als getrennte Checkliste
beschrieben. Diese Anleitung erklärt den Ablauf; sie ersetzt weder den
Preflight-Nachweis noch die Freigabe für Apply oder Neustart.

Der read-only Endpunkt `/api/v1/orchestration` meldet den Installationsstatus
von Helper und Discovery-Socket, die Integritätsprüfung und den Policy-Modus.
Fehlen Helper oder Socket, lautet der Status `unavailable`; daraus werden keine
Gastberechtigungen abgeleitet. Home Assistant zeigt denselben Zustand über die
Helper-Status-Entity. `discover_only` bleibt der sichere Standard.

## Stable-Vorbereitung: Komponenten und Grenzen

Die Home-Assistant-Integration wird über HACS installiert und aktualisiert;
der Proxmox-Agent ist ein unabhängig laufender Dienst. HACS verändert niemals
den Agenten. Vor einer Stable-Freigabe müssen Integration, Agent und API-
Vertrag getrennt aus dem exakten Release-Commit verifiziert werden. Die
Reihenfolge ist: Quelle/Commit prüfen, read-only Preflight ausführen,
Readiness- und TLS-Vertrag prüfen, erst dann einen ausdrücklich genehmigten
Apply durchführen. Rollback-Staging bleibt erhalten und wird nicht bereinigt.

TLS benötigt einen privaten Hostnamen oder eine private IP mit passendem SAN,
eine explizit vertrauenswürdige CA-Datei und aktivierte Zertifikatsprüfung.
HTTP-Fallback, `verify=False`, öffentliche Proxypfade und die Ausgabe von
Credentials sind nicht zulässig.

Die Funktionsmatrix bleibt klar begrenzt:

| Ziel | Unterstützter Zustand | Stable-Hinweis |
|---|---|---|
| Proxmox-Host | passiver Check und fester APT-Dry-Run | nur mit frischem Plan, TLS/API und Sicherheitsprüfung |
| LXC | vorbereiteter fester Helper-Pfad | laufend, OS/Paketmanager nachgewiesen, pro Ziel allowlistet |
| VM | dauerhaft ausgeschlossen | Karte zeigt Name/Status/Ressourcen und einen DE/EN-Hinweis; niemals `pct exec` oder einen anderen Update-Runner verwenden |
| Paketinstallation | nicht unterstützt | UI und API bleiben dauerhaft deaktiviert |

Installation, Update und Rollback sind getrennt zu dokumentieren. Ein
erfolgreicher Healthcheck des neuen Agenten ist kein Ersatz für die HA-
Nachkontrolle; umgekehrt ersetzt ein HACS-Update keinen Agent-Updatepfad.

### Fehlersuche vor Stable

- Bei `outdated` oder `incompatible`: Integration und Agent getrennt lesen,
  API 1.1 vergleichen und keinen Installationspfad freigeben.
- Bei TLS-Fehlern: SAN, CA-Pfad, Ablaufdatum und Schlüssel-Paar prüfen; nicht
  auf HTTP ausweichen.
- Bei Port-/Bind-Fehlern: Updater-Diagnose, systemd-Cgroup, Portzustände,
  `NRestarts`, `InvocationID` und monotone Startzeit prüfen; keine fremden
  Prozesse blind beenden.
- Bei Readiness-/Rollback-Fehlern: den offiziellen Rollback abwarten,
  Failed-/Previous-Staging erhalten und keinen zweiten Versuch starten.
- Bei Gast-Simulationen: LXC-Ziele nur nach expliziter Eignungs- und
  Autorisierungsprüfung betrachten; gestoppte Gäste werden nie gestartet.
  VMs bleiben dauerhaft ausgeschlossen und zeigen den Hinweis, dass Updates
  über das jeweilige Gastbetriebssystem durchzuführen sind. `pct exec` und
  andere Update-Runner werden für VM-Kennungen nie aufgerufen.

## 1. Voraussetzungen

- Proxmox VE mit systemd, Python 3 und `python3-venv`
- root-Zugriff für die Installation
- geprüfter Git-Commit des Projekts; keine unbestätigten Downloads
- private DNS-Adresse unter `.home.arpa`, `.lan` oder `.local` **oder** eine
  private IP-Adresse mit passendem IP-SAN im Agent-Zertifikat
- Zertifikat einer CA, der Home Assistant und der Agent vertrauen
- passender privater Schlüssel; Zertifikat und Schlüssel müssen zusammengehören
- freier interner Port ab 1024; Port 8128 des alten Dienstes wird nicht verwendet
- bestätigte Netzwerk-Allowlist; der Installer öffnet keine Firewallports
- private Proxmox-API-URL, Knotename und Proxmox-Credential mit Modus 600
- CA-Datei, die das Proxmox-Zertifikat validiert

Der Agent benötigt einen eigenen Servicebenutzer und verwendet ausschließlich
sein eigenes Installations-, Konfigurations- und Zustandsverzeichnis. Dateien
des bestehenden `homelab-wartung`-Systems werden nicht gelesen.

## 1a. Beta-Updates des Agenten getrennt von HACS

HACS aktualisiert ausschließlich die Home-Assistant-Integration und die
mitgelieferte Lovelace-Karte. Der separat laufende Agent auf Proxmox muss aus
dem gleichen geprüften Git-Commit separat aktualisiert werden. Vor einer
Freigabe ist der öffentliche Healthcheck lesend auf die erwartete
`agent_version` zu prüfen; Zugangsdaten werden dabei nicht ausgegeben.

Der sichere Ablauf ist: geprüften Commit bereitstellen, `install-agent.sh`
zunächst ohne `--apply` als Vorprüfung ausführen, die Quell- und
Versionsprüfung dokumentieren und erst nach einer getrennten Infrastruktur-
freigabe mit `--apply` die eigenen Agent-Dateien atomar aktualisieren. Der
Installer startet oder aktiviert den Dienst nicht. Dienstneustart und
Änderung der HA-Konfiguration bleiben getrennte, ausdrücklich freizugebende
Schritte. Ein HACS-Update allein darf nicht als Agent-Update betrachtet werden.

Ab Beta.18 meldet der Healthcheck zusätzlich `api_contract`; Home Assistant
zeigt `current`, `outdated`, `incompatible` oder `unknown` an. Eine
Versionsnummer allein reicht nicht für Kompatibilität.

Der vorbereitete gemeinsame Prozess liegt unter `scripts/upgrade-agent.sh`.
Ohne `--apply` ist er rein lesend. Der mutierende Pfad verlangt sowohl
`--apply` als auch `--confirm`, stoppt ausschließlich den Maintenance-Agenten,
installiert nur den geprüften Agent-Code und startet nur diesen Dienst. Bis
zum Healthcheck bleibt ein temporärer Rollback-Stand bestehen. Bei einem
fehlenden oder inkompatiblen Healthcheck wird der alte Code wiederhergestellt;
ein HACS-Update, ein HA-Neustart oder ein Agent-Start löst diesen Ablauf
niemals automatisch aus.

Nach jedem HACS-Update ist die Kompatibilitätssensorik zu prüfen. Bei
`outdated`, `incompatible` oder `unknown` bleibt der Agent unverändert und es
ist eine separate, ausdrücklich freigegebene Agent-Aktualisierung erforderlich.

### 1b. Historisches Rollback-Staging

`scripts/upgrade-agent.sh` löscht, verschiebt oder überschreibt vorhandene
`agent.previous.*.staging`-Verzeichnisse niemals automatisch. Ein vorhandener
Rollback-Stand blockiert den Ablauf weiterhin, wenn sein Inhalt nicht eindeutig
als historisch eingestuft werden kann. Die Vorprüfung akzeptiert mehrere alte
Stände nur dann, wenn alle eine lesbare Beta-Version tragen, die strikt älter
als die aktive Agent-Version ist, der Dienst aktiv ist und der aktuelle Agent
über den TLS-validierten API-Healthcheck erreichbar bleibt. Ein fehlender,
ungültiger, gleich neuerer oder mehrdeutiger Stand führt zu einem Abbruch mit
manueller Prüfung.

Beim eigentlichen, separat freizugebenden Austausch wird der neue Rollback-
Stand anhand der zuvor aktiven Agent-Version ausgewählt, nicht anhand einer
zufälligen Dateireihenfolge. Dadurch bleiben historische Staging-Daten
erhalten, während ein unklarer oder konkurrierender Upgrade-Zustand weiterhin
sicher blockiert wird.

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

Ein zusätzlicher DNS-Eintrag ist nicht erforderlich, wenn der Agent direkt über
eine private IP-Adresse angesprochen wird. In diesem Fall muss das Zertifikat
die Adresse als echten IP-SAN enthalten; ein DNS-Name im CN reicht nicht aus.
Die Home-Assistant-URL lautet dann beispielsweise:

```text
https://<PRIVATE_AGENT_IP>:48128
```

Alternativ kann ein bestätigter privater DNS-Name verwendet werden. Öffentliche
Proxies und Tunnel sind für die Agent-API nicht zulässig.

Die vorbereiteten Werkzeuge liegen unter `scripts/tls-agent.sh`. Mutierende
Aktionen benötigen immer sowohl `--apply` als auch `--confirm` und starten
keinen Dienst:

```bash
# Nur nach gesonderter Freigabe ausführen; der CA-Schlüssel bleibt auf dem
# administrativen, geschützten System und wird niemals nach HA übertragen.
sudo scripts/tls-agent.sh init-ca \
  --ca-dir /secure/smart-homelab-maintenance-ca \
  --apply --confirm

sudo scripts/tls-agent.sh issue \
  --ca-dir /secure/smart-homelab-maintenance-ca \
  --output-dir /secure/smart-homelab-maintenance-agent-cert \
  --ip <PRIVATE_AGENT_IP> \
  --apply --confirm

sudo scripts/tls-agent.sh verify \
  --ca-dir /secure/smart-homelab-maintenance-ca \
  --cert /secure/smart-homelab-maintenance-agent-cert/agent.crt \
  --key /secure/smart-homelab-maintenance-agent-cert/agent.key \
  --ip <PRIVATE_AGENT_IP>
```

Das öffentliche CA-Zertifikat wird später kontrolliert als `/ssl/<name>.pem`
in Home Assistant bereitgestellt und im Config Flow als CA-Pfad angegeben. Nur
das öffentliche CA-Zertifikat wird übertragen; CA- und Agent-Privatschlüssel
bleiben außerhalb von HA. Die Integration prüft weiterhin Zertifikatskette,
IP-SAN und Ablaufdatum und akzeptiert keinen HTTP-Fallback.

```bash
openssl x509 -in /etc/ssl/private/smart-homelab-agent.crt -noout -subject -issuer -dates
openssl x509 -in /etc/ssl/private/smart-homelab-agent.crt -noout -checkend 86400
openssl x509 -in /etc/ssl/private/smart-homelab-agent.crt -noout -checkip <PRIVATE_AGENT_IP>
```

Selbstsignierte Zertifikate ohne vertrauenswürdige CA, deaktivierte
Zertifikatsprüfung und Klartext-HTTP sind nicht zulässig. Der Installer prüft
Ablaufdatum und die Zuordnung von Zertifikat und Schlüssel.

### 3a. Einfacher lokaler Betrieb mit selbstsigniertem Zertifikat

Für einen ausschließlich lokalen Agenten kann statt einer separaten CA ein
selbstsigniertes Serverzertifikat verwendet werden. Das Zertifikat wird als
ausdrücklich vertrauenswürdige CA-Datei unter `/ssl/` in Home Assistant
hinterlegt. Dadurch bleibt die Prüfung aktiv; `verify=False`, eine Abschaltung
der Hostname-/IP-Prüfung oder ein HTTP-Fallback sind nicht erforderlich.

Die Erstellung bleibt ein separat freizugebender, mutierender Schritt:

```bash
sudo scripts/tls-agent.sh self-signed \
  --output-dir /secure/smart-homelab-maintenance-agent-cert \
  --ip <PRIVATE_AGENT_IP> \
  --prefix agent \
  --apply --confirm
```

Das Werkzeug erzeugt einen privaten Schlüssel mit Modus `0600` und ein
öffentliches Zertifikat mit Modus `0644`. Das Zertifikat enthält die private
IP-Adresse als echten IP-SAN, `basicConstraints=CA:FALSE`, `serverAuth` und
geeignete Key Usage. Nur die öffentliche Zertifikatsdatei wird kontrolliert
nach Home Assistant `/ssl/` übertragen und im Config Flow als CA-Datei
angegeben. Der Server-Privatschlüssel bleibt ausschließlich auf Proxmox.

Der Installer akzeptiert diesen Betriebsweg, weil er Zertifikatsablauf,
passenden Schlüssel und den IP-SAN prüft. Eine Zertifikatskette wird bei diesem
Modus nicht vorausgesetzt; die Vertrauensentscheidung erfolgt ausschließlich
durch die explizite CA-Datei im HA-Transport. Für mehrere Agenten oder längere
Betriebswege ist weiterhin die dedizierte CA-Variante vorzuziehen.

Bei Erneuerung muss ein neuer Dateipräfix verwendet werden. Vor dem Austausch
sind SAN, Ablauf, Schlüssel-Paar und die explizite Vertrauensprüfung erneut
isoliert zu prüfen. Ein Zertifikatswechsel, eine HA-Konfigurationsänderung und
ein Dienstneustart bleiben getrennte, freizugebende Schritte.

## 4. Vorprüfung

Die Vorprüfung verändert nichts:

Für eine maschinenlesbare, nicht mutierende Helper-Prüfung steht zusätzlich
der JSON-Vertrag bereit:

```bash
sudo scripts/lxc-helper-preflight.py \
  --source-dir /pfad/zum/geprüften-checkout \
  --expected-commit <40-stellige-sha>
```

Die Ausgabe enthält `decision` (`GO`/`NO-GO`), Einzelprüfungen,
`failed_checks`, `apply_authorization_required` und
`mutations_performed=false`. Auch bei `GO` ist eine separate Apply-Freigabe
erforderlich; der Befehl installiert, startet oder autorisiert nichts.

```bash
sudo scripts/install-agent.sh \
  --source-dir /tmp/smart-homelab-maintenance \
  --expected-commit <GEPRUEFTER_COMMIT> \
  --cert /etc/ssl/private/smart-homelab-agent.crt \
  --key /etc/ssl/private/smart-homelab-agent.key \
  --agent-host <PRIVATE_AGENT_IP> \
  --port 48128 \
  --proxmox-url https://<PROXMOX_PRIVATE_NAME>:8006/api2/json \
  --proxmox-node pve \
  --proxmox-ca /etc/ssl/certs/proxmox-ca.crt \
  --proxmox-token-file /etc/smart-homelab-maintenance/proxmox-api-token
```

Die Prüfung stoppt bei fehlenden Proxmox-/Python-Voraussetzungen, ungültigem
TLS, öffentlichem Host/IP-Ziel, fehlendem SAN, falschem Commit oder
unvollständiger Quelle.

## 4a. Erneuerung und Zertifikatswechsel

Erneuerungen werden zunächst in ein separates Verzeichnis ausgestellt und
geprüft. Die vorbereitete Rotation ersetzt anschließend nur die beiden eigenen
Agent-Dateien atomar; sie startet keinen Dienst und ändert keine CA:

```bash
sudo scripts/tls-agent.sh renew \
  --ca-dir /secure/smart-homelab-maintenance-ca \
  --output-dir /secure/smart-homelab-maintenance-renewal \
  --ip <PRIVATE_AGENT_IP> \
  --apply --confirm

sudo scripts/tls-agent.sh rotate \
  --ca-dir /secure/smart-homelab-maintenance-ca \
  --cert /secure/smart-homelab-maintenance-renewal/agent-renewed.crt \
  --key /secure/smart-homelab-maintenance-renewal/agent-renewed.key \
  --ip <PRIVATE_AGENT_IP> \
  --target-dir /etc/smart-homelab-maintenance \
  --apply --confirm
```

Vor jedem Wechsel sind Ablauf, CA-Kette, IP-SAN und Schlüssel-Paar zu prüfen.
Ein Dienstneustart und die Aktualisierung der HA-Konfiguration sind separate,
explizit freizugebende Schritte.

## 5. Installation

Erst nach separater Infrastrukturfreigabe darf der Apply-Schalter verwendet
werden:

```bash
sudo scripts/install-agent.sh \
  --source-dir /tmp/smart-homelab-maintenance \
  --expected-commit <GEPRUEFTER_COMMIT> \
  --cert /etc/ssl/private/smart-homelab-agent.crt \
  --key /etc/ssl/private/smart-homelab-agent.key \
  --agent-host <PRIVATE_AGENT_IP> \
  --port 48128 \
  --proxmox-url https://<PROXMOX_PRIVATE_NAME>:8006/api2/json \
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

Vor einem Stable-Update müssen die Checklistenpunkte für Quelle, TLS,
Readiness, systemd-Lebenszyklus und Rollback vollständig belegt sein. HACS
aktualisiert nur die HA-Integration; der Agent wird ausschließlich über den
offiziellen, separat freigegebenen Updater aktualisiert. Ein erfolgreicher
Preflight ohne `--apply` ist noch kein produktives Update.

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
Installations- und Starttest. Der reproduzierbare Root-/systemd-Installer-
Nachweis läuft separat über den GitHub-Actions-Job
`installer-systemd.yml` auf einem kurzlebigen Runner; ein übersprungener oder
nicht systemd-fähiger Runner gilt als NOT RUN und nicht als PASS. Auch ein
grüner CI-Job autorisiert keine Installation auf `pve-home`.
