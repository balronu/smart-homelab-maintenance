# Phase 4.19b – Lokales HTTPS ohne eigene Zertifizierungsstelle

**Projekt:** Smart Homelab Maintenance  
**Referenzstand:** `05f42ef`  
**Scope:** ausschließlich Offline-Implementierung und Mock-/Loopback-Tests

## Ergebnis

**GO für die isolierte technische Nutzung des lokalen selbstsignierten
Zertifikats.**  
**Kein GO für eine produktive Zertifikatserstellung oder Bereitstellung in
dieser Phase.**

Die bestehende CA-basierte Variante bleibt erhalten. Der neue Weg ist nur für
einen ausdrücklich lokalen, kontrollierten Betrieb vorgesehen.

## Technische Machbarkeit

Die Home-Assistant-Integration verwendet bereits:

- `ssl.create_default_context(cafile=...)`
- `CERT_REQUIRED`
- aktivierte Hostname-/IP-Prüfung
- auf `/ssl/` begrenzte CA-Dateipfade
- ausschließlich HTTPS-Agent-URLs

Ein selbstsigniertes End-Entity-Zertifikat mit `CA:FALSE` kann als explizit
hinterlegte Vertrauensdatei verwendet werden. Die TLS-Prüfung wird dabei nicht
abgeschwächt und unbekannte Zertifikate werden nicht automatisch übernommen.

## Implementierte Änderungen

- `scripts/tls-agent.sh` unterstützt zusätzlich `self-signed`.
- Die bestehende `init-ca`, `issue`, `renew`, `verify` und `rotate`-Logik blieb
  unverändert.
- Der neue Pfad benötigt weiterhin `--apply --confirm`.
- Erzeugt werden ein RSA-3072-Schlüssel (`0600`) und ein Zertifikat (`0644`).
- Das Zertifikat enthält IP-SAN, `CA:FALSE`, `serverAuth`,
  `digitalSignature` und `keyEncipherment`.
- Vor dem Erfolg werden Ablauf, IP-SAN, expliziter Trust Anchor,
  Server-Authentifizierung und Schlüssel-Paar geprüft.
- Keine Dienste werden gestartet oder neugestartet.

## Echte lokale TLS-Tests

Mit einem temporären lokalen HTTPS-Testserver wurden ausgeführt:

| Test | Ergebnis |
|---|---|
| Selbstsigniertes Zertifikat mit freigegebenem IP-SAN | PASS |
| Explizit hinterlegtes Zertifikat als Trust Anchor | PASS |
| Verbindung mit Standard-Truststore ohne Zertifikat | PASS – korrekt abgelehnt |
| Verbindung mit anderem Zertifikat | PASS – korrekt abgelehnt |
| Falscher IP-SAN | PASS – korrekt abgelehnt |
| `CA:FALSE` und `serverAuth` | PASS |
| Schlüsselberechtigungen 0600/0644 | PASS |
| Fehlende `--apply --confirm`-Freigabe | PASS – Änderung blockiert |
| Erneuerung mit neuem Präfix | PASS |

Die Tests nutzten ausschließlich Loopback und temporäre Testdaten. Es wurde
kein produktives Zertifikat und kein produktiver Schlüssel erzeugt.

## Installer-Kompatibilität

Der Installer prüft Ablaufdatum, IP-SAN und die Zuordnung von Zertifikat und
Schlüssel. Für den selbstsignierten Modus wird keine CA-Kette vorausgesetzt,
weil Home Assistant das Zertifikat separat als ausdrückliche CA-Datei lädt.
Der bestehende HTTPS- und SAN-Schutz bleibt aktiv.

## Unterstützte Betriebsarten

### A – Einfacher lokaler Betrieb

- selbstsigniertes Serverzertifikat
- öffentliche Zertifikatsdatei kontrolliert nach HA `/ssl/`
- Server-Privatschlüssel ausschließlich auf Proxmox
- keine eigene CA erforderlich
- geeignet nur für einen eng begrenzten lokalen Agentenweg

### B – Erweiterter Betrieb

- dedizierte private CA
- CA-signiertes Serverzertifikat
- CA-Privatschlüssel getrennt und offline verwaltet
- vorzuziehen bei mehreren Clients, mehreren Agenten oder längerer
  Zertifikatsverwaltung

## Offene Punkte und Grenzen

- Die produktive Zertifikatserstellung bleibt durch Phase 4.19/4.19a gesperrt,
  bis ein geeigneter Schlüssel-Speicher freigegeben ist.
- Die Übertragung nach HA `/ssl/` wurde nicht durchgeführt.
- Der Agent wurde nicht installiert oder gestartet.
- Es erfolgte keine Änderung an VM 104, Proxmox, DNS oder Firewall.
- Ein selbstsigniertes Zertifikat muss bei jeder Erneuerung explizit als
  Vertrauensdatei aktualisiert werden; sonst wird die Verbindung korrekt
  abgelehnt.

## Tests und CI

Lokaler fokussierter Lauf:

```text
python3 -m unittest -v tests.test_tls_self_signed tests.test_core tests.test_firewall_scripts
42 Tests, alle bestanden
```

Zusätzlich erfolgreich: Shell-Syntaxprüfung von `scripts/tls-agent.sh` sowie
manuelle Prüfung der Zertifikats- und Dateirechte im isolierten Temp-Verzeichnis.

GitHub Actions wurden für diese lokale Implementierungsphase nicht gestartet;
es wurde kein Merge und kein Release durchgeführt. Die vollständige CI ist vor
einem späteren PR-Merge erneut erforderlich.

## Schlussentscheidung

**Technische Offline-Validierung: GO.**  
**Produktive Zertifikatserstellung: NO-GO bis zur separaten Freigabe eines
sicheren Speicher- und Übertragungswegs.**
