# Phase 4.7 – Installationsbereitschaft

## Prüfgrenzen

Die Prüfung erfolgte am 2026-11-06 ausschließlich lesend. Es wurden keine
Dienste installiert, aktiviert oder gestartet, keine Tokens erzeugt, keine
Firewall-/DNS-Regeln geändert und keine produktiven Home-Assistant- oder
Proxmox-Daten verändert.

Repository-Referenz: PR #2, geprüfter Softwarestand
`849468b3e5a10ffeb47038ba94e0dba072cda5d8`.

## 1. Tatsächliche Hostvoraussetzungen

| Bereich | Befund | Status |
|---|---|---|
| Proxmox | Proxmox VE 9.2.0, Manager 9.2.26, laufender 7.0-PVE-Kernel | PASSED |
| Alter Wartungsdienst | HTTP-Dienst aktiv auf Port 8128; Unit und Timer unverändert | INFORMATION |
| Neuer Agent | Keine Agent-Unit und keine Agent-Verzeichnisse unter `/opt`, `/etc` oder `/var/lib` | BLOCKED für Starttest |
| Zielport | Port 48128 ist derzeit nicht belegt | PASSED, keine Freigabe zum Öffnen |
| Speicher | Root-Dateisystem ca. 60 % belegt, ca. 27 GB verfügbar | PASSED mit Reserveprüfung vor Installation |
| RAM/Swap | Host hat geringe aktuell verfügbare RAM-Reserve und nutzt Swap | WARNUNG; Installationstest ressourcenschonend planen |
| Firewall | Proxmox-Firewall ist nicht aktiv; keine gezielte Agent-Allowlist vorhanden | BLOCKED für Netzwerkfreigabe |

Der alte Dienst bindet weiterhin an alle lokalen IPv4-Adressen. Er wurde nicht
verändert. Der neue Agent darf deshalb nicht über diese bestehende Unit oder
deren Konfiguration betrieben werden.

## 2. Netzwerk, DNS und TLS

Der Host und VM 104 befinden sich im gleichen privaten Netz; ein lesender
Erreichbarkeitstest vom Host zur VM war erfolgreich. Eine laufende
Agent-Verbindung konnte naturgemäß nicht geprüft werden, weil Port 48128
geschlossen ist.

Es wurde kein stabiler DNS-Eintrag für einen Agenten gefunden. Der vorhandene
Proxmox-Knotenname gehört zur internen DNS-Zone und ist kein Nachweis, dass ein
neuer Agent-Name von HAOS aufgelöst werden kann.

Ein vorhandenes Proxmox-Zertifikat deckt den Proxmox-Webdienst und dessen
Knotennamen ab. Es ist kein dediziertes Agent-Zertifikat. Für den Agenten ist
ein eigenes Zertifikat mit passendem SAN für den späteren privaten Agent-DNS-
Namen und eine CA erforderlich, die HAOS vertraut. Eine Wiederverwendung des
Proxmox-Privatschlüssels ist nicht freigegeben und wird nicht empfohlen.

**Empfohlene spätere Adresse:**
`https://<dedizierter-privater-agent-name>:48128`

Der Platzhalter darf erst nach DNS-, Zertifikats- und Routing-Abnahme ersetzt
werden. Die Integration akzeptiert ausschließlich private HTTPS-Ziele; eine
freie öffentliche URL oder ungeschütztes HTTP ist ausgeschlossen.

## 3. Proxmox-API-Berechtigungen

Es existiert bereits ein Proxmox-Servicekonto mit einem Read-only-Monitoring-
Token. Die zugehörige Rolle enthält `Sys.Audit`, `VM.Audit`,
`VM.GuestAgent.Audit` und `Datastore.Audit`. Dieses Rollenmodell deckt die
geplanten lesenden Host-, LXC- und VM-Abfragen grundsätzlich ab.

Der vorhandene Token wurde nicht gelesen, nicht ausgegeben und nicht für einen
Test wiederverwendet. Eine formale Prüfung des tatsächlichen Tokenstatus und
eine Zuordnung zum neuen Agenten stehen noch aus. Vor einem kontrollierten
Test ist ausdrücklich zu entscheiden, ob ein dediziertes, auf den benötigten
Pfad begrenztes Credential bereitgestellt wird. In dieser Phase wurde kein
neuer Benutzer, keine Rolle und kein Token angelegt.

## 4. Installer-Dry-Run

| Prüfung | Ergebnis |
|---|---|
| `--help` und Optionsoberfläche | PASSED |
| Shell-Syntax | PASSED |
| Root-/Python-/systemd-/Proxmox-Voraussetzungen | auf dem Zielhost vorhanden |
| Exakter Quellcommit | BLOCKED – geprüfte Quelle liegt dort nicht vor |
| Agent-Zertifikat und privater Schlüssel | BLOCKED – dedizierte Dateien fehlen |
| Proxmox-CA und Credential-Datei | BLOCKED – noch nicht für Agentbetrieb bereitgestellt |
| `--apply` | NOT RUN, ausdrücklich ausgeschlossen |

Ein vollständiger Installer-Dry-Run gegen den Zielhost konnte daher nicht
sicher bis zur Commit- und Zertifikatsprüfung durchgeführt werden. Der
Installer stoppt erwartungsgemäß vor jeder Änderung, wenn diese Eingaben
fehlen. Es wurden keine Testdateien auf dem Host erzeugt.

Rollback ist ohne zusätzliche Backups grundsätzlich über die eigenen Agent-
Pfade möglich; eine Installation darf trotzdem erst nach einer separaten
Sicherung-/Rollback-Entscheidung freigegeben werden. Der alte Dienst liegt
außerhalb dieser Pfade und wird vom Installer nicht angefasst.

## 5. Home-Assistant-Verbindung

Die im Repository geprüfte Beta.2-Integration validiert private HTTPS-DNS-
Namen und verwendet TLS-Zertifikatsprüfung. Die tatsächlich in VM 104
installierte Version und deren gespeicherte Config-Entry-Konfiguration wurden
nicht verändert und in dieser Phase nicht live ausgelesen. Deshalb ist die
Annahme einer noch aktiven localhost-Beschränkung für die laufende Installation
nicht abschließend verifiziert.

Für den späteren Verbindungstest wird mindestens ein Build benötigt, der die
private HTTPS-Agent-URL, CA-/Hostname-Prüfung und Token-Auth der aktuellen
Beta.2-Codebasis enthält. Vor der Verbindung ist der installierte Stand in
VM 104 read-only zu verifizieren; eine Aktualisierung oder Installation ist
separat freizugeben.

## 6. Konkreter späterer Installationsablauf

1. Dedizierten privaten DNS-Namen und erlaubten Quellbereich festlegen.
2. Vertrauenswürdige CA und Agent-Zertifikat mit passendem SAN bereitstellen.
3. Minimal erforderliches Proxmox-Read-only-Credential ausdrücklich freigeben.
4. Geprüften Repository-Commit und die vier Installer-Eingaben (Agent-TLS,
   Proxmox-URL, CA, Credential) auf dem Host bereitstellen.
5. Vollständigen Installer-Dry-Run ausführen und Ausgabe geheimnisfrei prüfen.
6. Separat freigegebenen `--apply`-Schritt ausführen; der Dienst bleibt dabei
   deaktiviert und gestoppt.
7. Unit, Dateirechte, TLS und Port lokal prüfen; erst danach einen ausdrücklich
   freigegebenen Starttest durchführen.
8. Von HAOS aus ausschließlich die passive Health-/Capabilities- und
   Discovery-Kommunikation testen.

## 7. Automatisch erfüllbar vs. freigabepflichtig

**Bereits bzw. automatisch erfüllbar:**

- Softwarestand und Offline-CI sind geprüft.
- Zielport 48128 ist frei.
- Proxmox stellt ein grundsätzlich passendes Read-only-Rollenmodell bereit.
- Installer und systemd-Vorlage sind technisch vorbereitet.

**Freigabepflichtig/offen:**

- dedizierter DNS-Name, Routing und gezielte Firewall-Allowlist;
- dediziertes Agent-Zertifikat und HAOS-vertrauenswürdige CA;
- Auswahl oder Neuausstellung eines minimalen Agent-Credentials;
- Bereitstellung des geprüften Quellcommits und der geheimen Eingabedateien;
- Installation, Dienststart und HA-Verbindungstest.

## 8. Entscheidung

**NO-GO für den ersten kontrollierten Installationstest.**

Hauptgründe sind fehlende Agent-TLS-/Credential-Dateien, fehlender
Agent-DNS-Eintrag, fehlende Netzwerk-Allowlist und die noch nicht verifizierte
Konfiguration der laufenden Beta.2 in VM 104. Der nächste eng begrenzte Schritt
ist die Infrastrukturfreigabe für DNS/TLS/Read-only-Credential; danach kann ein
erneuter, vollständiger Dry-Run erfolgen.
