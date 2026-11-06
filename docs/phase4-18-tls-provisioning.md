# Phase 4.18 – Sichere TLS-Zertifikatsbereitstellung

**Projekt:** Smart Homelab Maintenance  
**Ausgangscommit:** `2b20e04`  
**Geplante Agent-Adresse:** `https://<PRIVATE_AGENT_IP>:48128`
**Ergebnis:** Vorbereitung **GO**, produktive Zertifikatserstellung **NO-GO**

## 1. Implementierte Werkzeuge

Neu: `scripts/tls-agent.sh`

Unterstützte, explizit getrennte Aktionen:

- `init-ca`: dedizierte RSA-3072-Test-/Betriebs-CA erstellen;
- `issue`: Serverzertifikat mit privatem IP-SAN ausstellen;
- `verify`: CA-Kette, Ablauf, IP-SAN und Schlüssel-Paar prüfen;
- `renew`: neues Zertifikat in einem separaten Zielverzeichnis ausstellen;
- `rotate`: geprüftes Zertifikat und Schlüssel atomar in ein eigenes Ziel
  übernehmen.

Schreibende Aktionen benötigen sowohl `--apply` als auch `--confirm`. Die
Skripte starten oder stoppen keine Dienste, ändern keine Firewall und erzeugen
keine HAOS-Dateien.

## 2. Sicherheitsmaßnahmen

- CA-Privatschlüssel: Modus 0600.
- Agent-Privatschlüssel: Modus 0600.
- Öffentliche Zertifikate: Modus 0644.
- Keine privaten Schlüssel, Token oder Passwörter in Ausgaben.
- Bestehende Dateien werden bei CA- und Ausstellungsschritten nicht
  überschrieben.
- Zertifikate müssen die private Agent-IP als echten IP-SAN enthalten.
- `openssl verify` prüft die CA-Kette; `openssl x509 -checkip` prüft die
  Zielidentität.
- Ablaufprüfung verlangt mindestens 24 Stunden Restgültigkeit.
- Es gibt keinen HTTP-Fallback und keine deaktivierbare TLS-Prüfung.
- Der CA-Privatschlüssel wird niemals nach Home Assistant übertragen.

## 3. Home-Assistant-Vertrauen

Die bestehende Integration akzeptiert den optionalen CA-Pfad nur unter
`/ssl/`. Dort wird später ausschließlich das öffentliche CA-Zertifikat
bereitgestellt. Die Integration verwendet weiterhin `CERT_REQUIRED` und
Hostname-/IP-Prüfung.

Die Bereitstellung nach HA `/ssl/` wurde nicht durchgeführt. Globale HAOS-
Vertrauenseinstellungen wurden nicht verändert.

## 4. Isolierter End-to-End-Test

Mit einer temporären Testumgebung wurden ausgeführt:

1. Test-CA erstellen;
2. Zertifikat für `<PRIVATE_AGENT_IP>` mit IP-SAN ausstellen;
3. Kette, IP-SAN und Schlüssel-Paar erfolgreich prüfen;
4. falsche IP-Adresse ablehnen;
5. Zertifikat einer unbekannten CA ablehnen;
6. abgelaufenes Zertifikat ablehnen;
7. Erneuerung ausstellen;
8. Zertifikatswechsel atomar in ein temporäres Zielverzeichnis vorbereiten;
9. Schlüsselberechtigungen 0600 verifizieren.

**Ergebnis: PASSED.** Alle Testdateien lagen ausschließlich unter einem
temporären Verzeichnis und wurden danach entfernt. Es wurden keine produktiven
Zertifikate oder Schlüssel erzeugt.

## 5. Dokumentation

`docs/AGENT_INSTALLATION.md` beschreibt nun:

- Erst-CA und IP-SAN-Zertifikat;
- geschützte Schlüsselablage;
- öffentliche CA-Bereitstellung nach HA `/ssl/`;
- Prüfung der Kette und Identität;
- Erneuerung und atomare Rotation;
- notwendige separate Neustart-/HA-Freigaben.

## 6. Tests

| Prüfung | Status |
|---|---|
| Python-Regression | **PASSED** – 39 Tests |
| Python-Compile | **PASSED** |
| Shell-Syntax | **PASSED** |
| TLS-Provisioning-Workflow mit Testartefakten | **PASSED** |
| Falscher IP-SAN | **PASSED** – abgelehnt |
| Unbekannte CA | **PASSED** – abgelehnt |
| Abgelaufenes Zertifikat | **PASSED** – abgelehnt |
| Produktive CA-/Zertifikatserstellung | **NOT RUN** – ausdrücklich verboten |
| HAOS-CA-Übertragung | **NOT RUN** – ausdrücklich verboten |
| Agent-Installation/Start | **NOT RUN** – ausdrücklich verboten |

Die Remote-CI wird nach dem Commit über PR #2 ausgeführt. Merge und Release
bleiben ausgeschlossen.

## 7. Erforderliche Freigaben

Vor einer tatsächlichen Einrichtung müssen separat freigegeben werden:

- Verwendung der konkreten Agent-IP und der Zertifikatspfade;
- geschützte CA-Schlüsselablage;
- Ausstellung des Agent-Zertifikats;
- kontrollierte Übertragung des öffentlichen CA-Zertifikats nach HA `/ssl/`;
- Agent-Installation und Dienststart;
- anschließender HA-Verbindungstest.

## 8. Entscheidung

**GO für die lokale Vorbereitung und isolierte CI-Validierung.**

**NO-GO für produktive Zertifikatserstellung und Bereitstellung.** Es wurden
keine Änderungen an Home Assistant VM 104, Proxmox, DNS, Firewall, Diensten,
Backups oder Snapshots vorgenommen.
