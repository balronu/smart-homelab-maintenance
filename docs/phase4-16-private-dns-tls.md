# Phase 4.16 – Private DNS und vertrauenswürdiges HTTPS

**Projekt:** Smart Homelab Maintenance  
**Code-Stand:** 0.1.0-beta.2  
**Status:** Vorbereitung abgeschlossen; produktive DNS-/TLS-Einrichtung **NO-GO**

## 1. Umfang und Sicherheitsgrenzen

Diese Phase wurde ausschließlich lesend auf der vorhandenen Infrastruktur und
mit lokalen Fixtures durchgeführt. Es wurden keine DNS-Einträge, Zertifikate,
privaten Schlüssel, HAOS-Truststores, Agent-Dienste oder Firewall-Regeln
erstellt bzw. verändert. Der bestehende Wartungsdienst und VM 104 blieben
unverändert.

## 2. DNS-Bestandsaufnahme

- Der Proxmox-Host verwendet den vorhandenen Tailscale-Resolver und lokale
  Host-Datei-Einträge; daraus folgt keine für HAOS nutzbare interne DNS-Zone.
- HAOS VM 104 verwendet den FRITZ!Box-Resolver sowie IPv6-DNS; der HAOS-DNS-
  Dienst meldet keine zusätzlichen lokalen DNS-Server.
- Der Beispielname `smart-homelab.home.arpa` wurde sowohl vom lokalen Resolver
  als auch aus HAOS heraus als nicht vorhanden (NXDOMAIN) beobachtet.
- Der lokale Proxmox-Name ist auf dem Host über `/etc/hosts` bekannt, aber aus
  HAOS nicht auflösbar. Er ist daher kein stabiler Agent-Endpunkt.
- Es wurde kein bestehender interner DNS-Dienst gefunden, der für den Agenten
  ohne zusätzliche Infrastruktur verwendet werden könnte.

### Empfehlung

Vor einer Installation muss ein einzelner, stabiler privater FQDN in einer
bereits verwalteten internen DNS-Zone angelegt werden. `home.arpa` ist dafür
als private Namensdomäne geeignet, der konkrete Name darf aber erst nach
Bestätigung des tatsächlich zuständigen DNS-Dienstes festgelegt werden. Ein
manueller `/etc/hosts`-Eintrag auf nur einem System ist für HAOS nicht
ausreichend.

FRITZ!Box-Lokal-DNS kann nur verwendet werden, wenn ein entsprechender
statischer Host-Eintrag nachweislich unterstützt und von HAOS zuverlässig
aufgelöst wird. Alternativ wäre ein bereits genehmigter interner Resolver
erforderlich. Ein neuer DNS-Dienst wurde in dieser Phase nicht eingerichtet.

Cloudflare Tunnel und der vorhandene Reverse-Proxy sind für diesen Zweck nicht
geeignet: Der Agent darf nicht über einen öffentlichen oder allgemein
exponierten Pfad erreichbar werden.

## 3. TLS-Bestandsaufnahme und Zielbild

Das vorhandene Proxmox-Zertifikat ist für die Proxmox-Verwaltung ausgestellt
und wird nicht für den Agenten wiederverwendet. Es existiert kein nachgewiesenes
Agent-Zertifikat mit passendem SAN und keine für HAOS validierte private CA.

Empfohlenes Zielbild:

1. Dedizierte interne CA oder bereits genehmigter interner Zertifikatsdienst.
2. Eigenes Agent-Serverzertifikat mit dem später bestätigten privaten FQDN als
   Subject Alternative Name.
3. Privater Schlüssel ausschließlich auf dem Agent-Host, root-lesbar bzw. mit
   einer dedizierten Dienstberechtigung; kein Schlüssel in HA, Logs, Git oder
   API-Antworten.
4. CA-Zertifikat separat und nachvollziehbar in HA bereitstellen; die
   Zertifikatsprüfung bleibt vollständig aktiviert.
5. Erneuerung durch atomaren Austausch nach SAN-, Ketten- und Ablaufprüfung.
   Ein Agent-Neustart wäre erst in einem separat freigegebenen Wartungsfenster
   zulässig.

Es wurden keine Zertifikate oder privaten Schlüssel erzeugt oder ausgelesen.

## 4. Isolierte Integrationsänderung

Die Integration unterstützt nun optional einen integrationsspezifischen
CA-Dateipfad:

- Config-Flow-Feld `ca_file` (optional).
- Nur absolute Zertifikatspfade unter `/ssl/` werden akzeptiert.
- Pfad-Traversal, relative Pfade und Nicht-Zertifikatsendungen werden abgelehnt.
- Der Transport verwendet weiterhin `CERT_REQUIRED` und Hostname-Prüfung.
- Coordinator und Config-Flow reichen den CA-Pfad an den bestehenden Transport
  weiter; es wurde keine zweite Wartungslogik eingeführt.
- Leere Eingabe bedeutet ausschließlich die normale System-CA; sie deaktiviert
  TLS-Prüfung nicht.

Diese lokale Funktion ist noch kein Nachweis, dass eine CA bereits in HAOS
vorliegt. Der spätere Betrieb benötigt weiterhin einen kontrollierten,
unterstützten Weg, die öffentliche CA-Datei nach `/ssl/` zu bringen.

Die Home-Assistant-Sicherheitsleitfäden empfehlen TLS-Prüfung und den
gemeinsamen HTTP-Client mit aktivierter Zertifikatsprüfung; individuelle CAs
werden als explizite Konfigurationsoption behandelt:
[HA-Integrations-Sicherheit](https://contributors.home-assistant.io/security/guides/integrations/),
[Security-Helper](https://contributors.home-assistant.io/security/reference/helpers/).
Die HA-HTTP-Dokumentation beschreibt `/ssl` als persistenten SSL-Pfad, beweist
aber nicht allein eine automatische Vertrauensstellung für beliebige
Integrationen: [HTTP-Integration](https://www.home-assistant.io/integrations/http).

## 5. Spätere Einrichtungsschritte (nicht ausgeführt)

1. Internen DNS-Verantwortlichen und den tatsächlich unterstützten Resolver
   bestätigen.
2. Einen dedizierten privaten Agent-FQDN und den A-/AAAA-Umfang festlegen.
   Nicht benötigte IPv6-Erreichbarkeit darf nicht ungeschützt entstehen.
3. CA- und Zertifikatsaussteller sowie Erneuerungsprozess freigeben.
4. Zertifikat mit exakt passendem SAN ausstellen und Kette offline prüfen.
5. Agent-Schlüssel geschützt auf dem vorgesehenen Host ablegen.
6. Agent ausschließlich per HTTPS auf Port 48128 konfigurieren; kein
   HTTP-Fallback.
7. CA-Datei kontrolliert unter `/ssl/` bereitstellen und Config Flow mit dem
   privaten FQDN und CA-Pfad testen.
8. DNS-Auflösung aus HAOS, TLS-Hostname-Prüfung, Token-Authentifizierung und
   bestehende Dienste in einem gesondert freigegebenen Test prüfen.

## 6. Tests

| Prüfung | Ergebnis |
|---|---|
| Offline-Regressionstests | **PASSED** – 38 Tests |
| Python-Compile-Check | **PASSED** |
| JSON-/Übersetzungsprüfung | **PASSED** |
| CA-Pfad-Policy inkl. Traversal- und Endungsprüfung | **PASSED** |
| DNS-Auflösung des Beispielnamens | **BLOCKED/NO-GO** – NXDOMAIN |
| Vertrauenswürdige Agent-CA vorhanden | **BLOCKED** – nicht vorhanden/nicht nachgewiesen |
| Produktiver DNS-/TLS-Test | **NOT RUN** – ausdrücklich nicht freigegeben |
| HAOS-Installation oder CA-Installation | **NOT RUN** – ausdrücklich verboten |

Die vollständige Remote-CI muss nach dem Commit dieses isolierten Changes über
PR #2 erneut ausgeführt werden; ein CI-Ergebnis wird erst nach dem tatsächlichen
Lauf berichtet.

## 7. Freigaben und Risiken

Noch erforderlich:

- Freigabe eines internen DNS-Verfahrens und eines konkreten Namens.
- Freigabe einer vertrauenswürdigen CA sowie des Erneuerungsprozesses.
- Nachweis, wie die CA-Datei sicher nach HAOS `/ssl/` gelangt.
- Spätere Freigabe für Agent-Installation und HA-Konfiguration.

Restrisiken:

- Ein privater DNS-Name ohne funktionierende HAOS-Auflösung führt zu
  Verbindungsfehlern.
- Ein Zertifikat ohne exakten SAN oder ohne HA-vertrauenswürdige CA wird korrekt
  abgelehnt.
- IPv6 darf nicht versehentlich einen ungeschützten alternativen Agent-Pfad
  eröffnen.
- Eine private CA-Datei allein ersetzt keine Netzwerkzugriffskontrolle und
  keine Token-Authentifizierung.

## 8. Entscheidung

**NO-GO für die tatsächliche DNS-/TLS-Einrichtung und Agent-Verbindung.**

**GO für die isolierte Code-Vorbereitung**, weil die bestehende TLS-Prüfung
  erhalten bleibt und die CA-Eingabe nun eng begrenzt validiert wird.

Es wurden keine produktiven Systeme, DNS-Einträge, Zertifikate, Schlüssel,
Firewall-Regeln oder Dienste verändert.
