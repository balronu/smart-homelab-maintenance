# Phase 4.17 – HTTPS ohne zusätzlichen DNS-Dienst

**Projekt:** Smart Homelab Maintenance  
**Ausgangscommit:** `d09800d`  
**Ziel:** IP-basierte, weiterhin vollständig geprüfte HTTPS-Verbindung  
**Status:** Code-Vorbereitung **GO**, tatsächliche Zertifikatserstellung **NO-GO**

## 1. Ergebnis

Eine Verbindung zu einer privaten IPv4-Adresse ist technisch geeignet, wenn
das Agent-Zertifikat die Zieladresse als echten `iPAddress`-SAN enthält. Ein
DNS-Name im Common Name allein genügt nicht. Die geplante Form ist:

```text
https://<PRIVATE_AGENT_IP>:48128
```

Die vorhandene HA-Transportvalidierung akzeptiert bereits private IP-Ziele,
verlangt HTTPS und aktiviert weiterhin `CERT_REQUIRED` sowie Hostname-/IP-
Prüfung. Öffentliche IP-Adressen und Klartext-HTTP bleiben gesperrt.

## 2. Implementierte Änderungen

### Installer und Zertifikatsprüfung

- `scripts/agent-common.sh` akzeptiert nun private IP-Adressen zusätzlich zu
  privaten DNS-Suffixen.
- Öffentliche und nicht zugelassene IP-Ziele werden weiterhin abgelehnt.
- Der Installer übergibt das konfigurierte Agent-Ziel an die Zertifikatsprüfung.
- `openssl x509 -checkip` wird für IP-Ziele verwendet.
- Für DNS-Ziele wird `openssl x509 -checkhost` verwendet.
- Zertifikat/Schlüssel-Paar, Ablaufzeit und passender SAN müssen erfolgreich
  geprüft werden.
- Keine TLS-Prüfung und keine Hostname-/IP-Prüfung kann deaktiviert werden.

### Integration

Die bestehende Integration benötigte für die URL selbst keine Lockerung:

- `https://192.168.178.199:48128` wird als private URL akzeptiert.
- `http://...` wird abgelehnt.
- Öffentliche Ziele wie `https://8.8.8.8:48128` werden abgelehnt.
- Der optionale CA-Pfad bleibt auf `/ssl/` begrenzt.

## 3. Zertifikatsverfahren

Die folgenden Schritte sind ein späterer, separat freizugebender Ablauf und
wurden nicht ausgeführt:

1. Dedizierte interne CA in einer geschützten Administrationsumgebung
   bereitstellen. Der CA-Privatschlüssel bleibt ausschließlich dort.
2. Agent-Schlüssel auf dem Agent-Host erzeugen bzw. geschützt bereitstellen;
   niemals an Home Assistant übertragen.
3. Zertifikatsanfrage mit IP-SAN für die konkrete private Agent-Adresse
   erstellen und durch die interne CA signieren.
4. Zertifikat und Kette auf dem Agent-Host mit `openssl x509 -checkip` sowie
   Ablauf- und Schlüsselprüfung validieren.
5. Nur das öffentliche CA-Zertifikat nach HA `/ssl/` übertragen. Der private
   CA-Schlüssel bleibt außerhalb von HA.
6. Zertifikate vor Ablauf atomar ersetzen, Kette/SAN/Schlüssel prüfen und erst
   nach einer gesonderten Wartungsfreigabe den Agenten neu starten.
7. Bei Widerruf oder Austausch den alten öffentlichen Vertrauensanker aus HA
   entfernen, den neuen CA-/Zertifikatspfad testen und die alte Agent-Identität
   nicht parallel weiterverwenden.

Beispiel für die spätere, nicht ausgeführte Prüfung:

```bash
openssl x509 -in agent.crt -noout -checkend 86400
openssl x509 -in agent.crt -noout -checkip <PRIVATE_AGENT_IP>
```

Es wurden keine CA, Zertifikate oder Schlüssel erzeugt.

## 4. Sicherheitsbewertung

- IP-SAN verhindert, dass ein Zertifikat für einen anderen Namen akzeptiert
  wird.
- Die private CA wird nicht nach HA übertragen; nur ihr öffentliches
  Zertifikat ist erforderlich.
- Token-Authentifizierung bleibt zusätzlich verpflichtend.
- Die bestehende Firewall-Allowlist und IPv6-Sperre bleiben unverändert.
- Kein HTTP-Fallback, kein öffentlicher Tunnel und keine beliebige URL-Freigabe.
- Der Agent bleibt auf Port 48128 und ausschließlich intern vorgesehen.

Ein IP-Zertifikat ersetzt weder Netzwerkzugriffskontrolle noch Token-
Authentifizierung. Bei späterer Änderung der Agent-IP ist ein neues
Zertifikat mit neuem IP-SAN erforderlich.

## 5. Tests

| Prüfung | Ergebnis |
|---|---|
| Shell-Syntax für Installer/Helfer | **PASSED** |
| Private IPv4-URL in der Integration | **PASSED** |
| Öffentliche IPv4-URL | **PASSED** – abgelehnt |
| HTTP-Ziel | **PASSED** – abgelehnt |
| Offline-Regression vor dieser Änderung | **PASSED** – 38 Tests |
| Produktive Zertifikatsprüfung | **NOT RUN** – keine Zertifikate vorhanden/erzeugt |
| Agent-Installation | **NOT RUN** – nicht freigegeben |
| HA VM 104 | **NOT RUN** – produktives System |

Die vollständige CI wird nach dem Commit dieses Changes über PR #2 ausgeführt.

## 6. Offene Freigaben

- konkrete Agent-IP und Bind-Adresse bestätigen;
- interne CA und Aufbewahrungsort des CA-Schlüssels freigeben;
- Verfahren zur Bereitstellung des öffentlichen CA-Zertifikats nach HA `/ssl/`
  festlegen;
- Serverzertifikat mit IP-SAN ausstellen;
- Agent-Installation und anschließenden isolierten Verbindungscheck separat
  freigeben.

## 7. Entscheidung

**GO für die isolierte Implementierung und CI-Validierung.**

**NO-GO für die tatsächliche Zertifikatserstellung, Agent-Installation und
HA-Konfiguration**, bis IP, CA-Vertrauen und die geschützte Schlüsselablage
ausdrücklich festgelegt und freigegeben sind.

Produktive HA-, Proxmox-, DNS-, Firewall- und Zertifikatszustände wurden nicht
verändert.
