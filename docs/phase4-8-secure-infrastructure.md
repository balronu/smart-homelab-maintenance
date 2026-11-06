# Phase 4.8 – Sichere Agent-Infrastruktur

## Prüfgrenzen

Die Bestandsaufnahme erfolgte am 2026-11-06 ausschließlich lesend. Es wurden
keine DNS- oder Firewall-Regeln geändert, keine Zertifikate oder Tokens
erstellt, keine Dienste installiert/gestartet und VM 104 sowie der bestehende
Wartungsdienst nicht verändert.

Der aktuelle Softwarestand bleibt PR #2, Commit
`b2c30416b01bf13260411a7a9d4938ed3c0f2141`.

## 1. Empfohlene DNS-Lösung

Cloudflare Tunnel ist für diesen Agenten **nicht geeignet**. Der vorhandene
Connector läuft token-managed und führt zu Nginx Proxy Manager. Dort werden
öffentliche Web-Hostnamen verarbeitet. Ein Agent-Endpunkt über diesen Tunnel
würde die gewünschte private Erreichbarkeit nicht beweisen und könnte die API
öffentlich sichtbar machen.

Tailscale ist auf dem Proxmox-Host vorhanden, aber VM 104 war in der lesend
geprüften Peer-Liste nicht als erreichbarer Teilnehmer nachweisbar. Tailscale
kann später als privater Transport dienen, jedoch erst nachdem HAOS bewusst
demselben Tailnet beigetreten ist und eine Quell-Allowlist nachgewiesen wurde.

**Empfehlung:** zunächst ein dedizierter Name in der bestehenden privaten DNS-
Zone, der ausschließlich intern auf den Proxmox-Agenten zeigt. Kein Cloudflare-
Tunnel und kein öffentlicher DNS-Eintrag. Falls private DNS-Auflösung von HAOS
nicht gewährleistet werden kann, ist ein kontrollierter Tailscale-Pfad die
zweite Option.

## 2. Empfohlene TLS-Lösung

Der Agent soll auf Port 48128 mit einem eigenen Zertifikat und privatem
Schlüssel laufen. Das Zertifikat muss:

- den dedizierten privaten Agent-DNS-Namen im SAN enthalten;
- von einer CA stammen, der HAOS vertraut;
- mindestens TLS 1.2 erlauben;
- getrennt vom Proxmox-Webzertifikat und dessen Schlüssel verwaltet werden.

Das vorhandene Proxmox-Zertifikat ist kein Nachweis für ein Agent-Zertifikat.
Der Proxmox-Privatschlüssel wird nicht wiederverwendet.

## 3. Netzwerk-Schutzkonzept

Aktueller Befund:

- Port 48128 ist frei;
- die Proxmox-Firewall ist deaktiviert;
- der alte Wartungsdienst auf Port 8128 bleibt davon getrennt;
- der Cloudflare-Tunnel ist kein geeigneter Schutzmechanismus für die Agent-
  API;
- ein HAOS-Tailscale-Peer ist nicht nachgewiesen.

Damit ist der geforderte Quell-IP-Schutz aktuell **nicht wirksam nachgewiesen**.
TLS und Bearer-Token sind zusätzliche Anwendungsschutzschichten, ersetzen aber
keine Netzwerk-Allowlist.

Vor einer Bereitstellung muss genau eine der folgenden Schutzvarianten
freigegeben und getestet werden:

1. Host-/Proxmox-Firewallregel: TCP 48128 nur von VM 104 und ausdrücklich
   benannten Administrationsquellen, alles andere ablehnen; oder
2. gleichwertige vorgelagerte private Firewall/VLAN-Regel; oder
3. Tailscale-only-Bind/Route mit verifiziertem HAOS-Peer und enger ACL.

Keine dieser Varianten wurde aktiviert oder verändert.

## 4. Minimale Proxmox-Berechtigungen

Der Agent verwendet derzeit nur lesende Endpunkte für Node-Status, LXC-Liste
und VM-Liste. Als minimale Kandidatenrolle ist daher vorgesehen:

```text
Sys.Audit, VM.Audit
```

`Datastore.Audit` wird nur benötigt, wenn später Storage-/Datastore-Metriken
über die API ergänzt werden. `VM.GuestAgent.Audit` ist für den aktuellen Code
nicht erforderlich, da keine Guest-Agent-Abfragen ausgeführt werden.

Die bestehende Monitoring-Rolle enthält zusätzliche Audit-Rechte und wurde
nicht für den Agenten verwendet. Vor dem Installationstest ist ein dediziertes
Credential mit der kleinsten bestätigten Rolle bereitzustellen. Es wurden keine
Tokens oder Benutzer angelegt.

## 5. Installer-Konfigurationsvorlage

Eine vollständige geheimnisfreie Vorlage liegt unter
[`deploy/agent.toml.example`](../deploy/agent.toml.example). Sie enthält nur
private Platzhalter, den Agent-Port, TLS-Pfade und die Proxmox-API-Adresse.

Die beiden Secrets gehören nicht in TOML, Logs oder die Home-Assistant-Karte.
Die systemd-Unit lädt sie getrennt als:

```text
api_token
proxmox_api_token
```

Für den Installer sind zusätzlich ein geprüfter Quellcommit, ein Agent-
Zertifikat/-Schlüssel, eine Proxmox-CA-Datei und ein vorhandenes Proxmox-
Credential mit Modus 600 erforderlich. Der Installer aktiviert und startet den
Dienst nicht automatisch.

## 6. Noch notwendige Freigaben

- privater Agent-DNS-Name und HAOS-Auflösung;
- eine der drei wirksamen Netzwerk-Allowlist-Varianten;
- dediziertes Agent-Zertifikat samt vertrauenswürdiger CA;
- dedizierte minimale Proxmox-Rolle und Credential;
- isolierter Installer-Dry-Run mit dem geprüften Commit;
- ausdrückliche Freigabe für Installation, Dienststart und HA-Verbindungstest.

## 7. Sicherheitsprüfung

- ungeschütztes HTTP: im Agent-Code nicht zugelassen;
- öffentliche Bind-Adresse: durch Runtime-Konfiguration ausgeschlossen;
- Secrets in Logs: systemd-Credentials und Redaction vorgesehen;
- Zugriff auf alten Dienst: keine gemeinsame Konfiguration oder Pfade;
- Updates/Wartungsbefehle: global deaktiviert;
- automatische Starts: Installer führt weder `enable` noch `start` aus.

## 8. Entscheidung

**NO-GO für die Bereitstellung der Infrastruktur.**

Die Software- und Credential-Struktur ist vorbereitet, aber ein wirksamer
Netzwerkschutz, ein privater Agent-DNS-Namen, ein HAOS-Transportpfad und ein
dediziertes TLS-/Proxmox-Credential fehlen noch. Der nächste begrenzte Schritt
ist die Freigabe und Umsetzung genau einer privaten Transport-/Allowlist-
Variante; anschließend folgt ein erneuter Read-only-Audit vor jeder
Installation.
