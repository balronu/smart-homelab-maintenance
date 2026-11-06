# Phase 4.19 – Produktive CA und Serverzertifikat

**Projekt:** Smart Homelab Maintenance  
**Version:** 0.1.0-beta.2  
**Geprüfter Commit:** `05f42ef`  
**Geplanter Agent:** private HTTPS endpoint on the approved agent port

## Ergebnis

**NO-GO für Phase 4.20.**

Die ausdrücklich freigegebene Zertifikatserstellung wurde nicht begonnen, weil
vorher kein geeigneter, dauerhaft geschützter Speicherort für den privaten
CA-Schlüssel nachgewiesen werden konnte. Es wurde keine unsichere Ersatzlösung
verwendet.

## Speicherprüfung

Die Prüfung erfolgte ausschließlich lesend:

- Der Workspace liegt auf einem schreibbaren ext4-Root-Dateisystem.
- Ein verschlüsseltes oder anderweitig nachweisbar geschütztes dediziertes
  Administrationsmedium konnte nicht bestätigt werden.
- `/root` und mehrere OpenClaw-Verzeichnisse sind zwar auf `0700` beschränkt,
  aber diese Berechtigung allein belegt weder eine geeignete Schlüssel-
  lebensdauerverwaltung noch eine getrennte, für Erneuerungen vorgesehene
  Administrationsablage.
- Das Projekt- und Arbeitsverzeichnis ist kein geeigneter CA-Schlüsselspeicher;
  es enthält Quellcode und Git-Daten und ist für Projektarbeit bestimmt.
- Der gefundene System-CA-Bundle unter `/etc/ssl/certs/` ist ein öffentlicher
  Vertrauensspeicher und kein sicherer Speicher für einen privaten CA-Schlüssel.

Damit ist die Anforderung „sicherer Speicherort vor Erstellung nachweisen“
nicht erfüllt.

## Zertifikatsstatus

| Prüfung | Ergebnis |
|---|---|
| Dedizierte CA erstellt | Nein |
| Serverzertifikat erstellt | Nein |
| Freigegebener IP-SAN geprüft | Nicht ausgeführt |
| Zertifikatskette/Fingerprints | Nicht anwendbar |
| Neue Schlüsselberechtigungen | Keine neuen Dateien |
| CA-Schlüssel nach HA oder Agent übertragen | Nein |

Das Werkzeug `scripts/tls-agent.sh` bleibt unverändert. Seine isolierte
Testvalidierung aus Phase 4.18 wurde nicht als produktive Zertifikatserstellung
ausgegeben.

## Erforderlicher nächster Schritt

Vor Phase 4.20 muss ein bestehender, administrativ kontrollierter und dauerhaft
geschützter Speicherort benannt und nachgewiesen werden. Er muss außerhalb des
Git-Repositories und außerhalb des künftigen Agenten liegen, nur für berechtigte
Administratoren zugänglich sein und für spätere Erneuerungen verfügbar bleiben.

Erst danach dürfen `init-ca` und `issue` mit dem geprüften TLS-Werkzeug
ausgeführt werden. Anschließend sind Kette, Ablaufdatum, Schlüsselpaare,
Dateimodi, Server-Authentifizierung und `openssl x509 -checkip <AGENT_IP>` zu
prüfen. Der CA-Privatschlüssel darf weder an Home Assistant
noch an den Agenten übertragen werden.

## Unverändert geblieben

Es wurden keine produktiven Zertifikate oder Schlüssel erstellt. Es gab keine
Änderungen an Proxmox, Home Assistant VM 104, DNS, Firewall, Agent-Dienst,
Tokens, Backups, Snapshots, Releases oder bestehenden Wartungsdiensten.

## Tests und CI

Keine produktive Zertifikatsprüfung war möglich und daher nicht ausgeführt.
Es gab keine Quellcodeänderung; lokale CI- und GitHub-Actions-Läufe wurden für
diese blockierte Phase nicht gestartet. Die in Phase 4.18 separat durchgeführte
isolierte TLS-Werkzeugprüfung bleibt davon unberührt.
