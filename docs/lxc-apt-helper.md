# Sicherer LXC-APT-Helper (Beta.21-Kandidat)

## Befund

Der produktive Agent läuft als `smart-homelab-maintenance` und kann den
Proxmox-IPC-/ACL-Pfad von `pct` nicht lesen. Eine direkte `sudo`-Freigabe für
`pct` wäre zu weitreichend, weil damit beliebige Proxmox-Operationen und freie
Gastbefehle erreichbar wären.

## Architektur

Der Kandidat trennt die Privilegiengrenze vom Agenten:

1. Ein root-owned Helper wird später unter
   `/usr/libexec/smart-homelab-maintenance/lxc-apt-helper` installiert.
2. Ein root-owned systemd-Dienst stellt einen Unix-Socket unter
   `/run/smart-homelab-maintenance/lxc-apt-helper.sock` bereit. Der Agent
   übergibt dort ein JSON-Objekt über einen Socket mit enger Gruppenberechtigung.
   Jeder Client wird zusätzlich per `SO_PEERCRED` auf die exakte UID des
   Dienstbenutzers `smart-homelab-maintenance` geprüft. Es gibt keine Befehls-,
   Pfad- oder Credential-Parameter.
3. Der Helper liest eine separate, root-owned Allowlist
   `/etc/smart-homelab-maintenance/lxc-apt-allowlist.toml`.
4. Er akzeptiert nur numerische, allowlistete CT-IDs und die Operationen
   `read` und `simulate`.
5. Die root-owned Allowlist wird bei jedem Socket-Aufruf neu gelesen und
   geprüft. Vor jedem Gastaufruf wird `pct status <id>` gelesen. Alles außer
   exakt `status: running` wird abgewiesen; Container werden nie gestartet.
   Ein zwischen Statusprüfung und `pct exec` gestoppter Container führt zu
   einem sicheren Fehler; der feste `pct exec`-Pfad kann daraus keinen Start-,
   Installations- oder beliebigen Befehlspfad machen.
6. Die einzigen Gastargv sind:
   - read: `/usr/bin/apt list --upgradable`
   - simulate: `/usr/bin/apt-get --simulate --no-remove -o
     Debug::NoLocking=true upgrade`
7. Alle Aufrufe verwenden Argumentlisten ohne Shell, ein 10-Sekunden-Limit,
   ein 10-Sekunden-Socket-Limit und eine maximal gestreamte kombinierte
   Ausgabegröße von 256 KiB. Prozesse werden bei Timeout oder Ausgabelimit
   beendet und aufgeräumt.

Die Simulation bleibt eine ausdrücklich angeforderte Simulation. Der Helper
enthält keinen Installations-, Entfernungs-, `apt update`- oder Neustartpfad.

## Allowlist-Format (nur Vorschlag, nicht aktiv)

```toml
[containers."101"]
authorized = true
os_name = "Debian"
os_version = "13"
package_manager = "apt"
```

Die Datei muss root-owned und für den Agenten nicht beschreibbar sein. Ein
Eintrag autorisiert nur die festgelegten Prüfoperationen; er autorisiert keine
Anwendungsupdates. Der Agent übernimmt die Beta.20-Allowlist erst, wenn der
Helper ausdrücklich aktiviert ist. Standard bleibt deaktiviert.

## systemd-/Socket-Grenze

Die spätere Installation verwendet den mitgelieferten separaten root-owned
Dienst `scripts/smart-homelab-maintenance-lxc-helper.service` mit diesen
sicherheitsrelevanten Eigenschaften:

```ini
[Service]
User=root
Group=smart-homelab-maintenance
ExecStart=/usr/libexec/smart-homelab-maintenance/lxc-apt-helper --serve
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
RestrictAddressFamilies=AF_UNIX
```

Der Socket wird `root:smart-homelab-maintenance` mit Modus `0660`; zusätzlich
prüft der Dienst die Peer-Credentials und akzeptiert nur die Agent-UID. Vor einer
produktiven Freigabe müssen Besitzer, Modus, Hash/Quelle des Helpers,
Allowlist-Besitzer, Socket-Gruppe und die effektive Dienstisolierung separat
geprüft werden. Der bestehende Agent mit `NoNewPrivileges=true` muss keine
Privilegien erhöhen. Es gibt keine `pct`- oder `NOPASSWD: ALL`-Freigabe.

## Vertrauensgrenze und Risiken

Gastantworten sind untrusted data. Der Agent darf daraus nur Paketstatus
anzeigen; er darf keine Gastantwort in einen Befehl, Pfad oder eine neue
Allowlist-Regel umwandeln. APT-Cache-Daten können veraltet oder manipuliert
sein und werden daher mit Zeitstempel/Status angezeigt. Anwendungsdatenbanken,
dirty Git-Repositories und migrationskritische Dienste sind nicht durch einen
OS-APT-Check abgedeckt.

## Aktivierungs-Gates

Vor einer Aktivierung müssen in einem separaten Auftrag alle folgenden Gates
grün sein: root-owned Installation, statische Hash-/Modusprüfung, exakte
Socket-/Dienstregel, Allowlist-Review pro CT, laufender Status, erfolgreicher
passiver Read-Test, negativer Test für nicht allowlistete IDs, negativer Test
für gestoppte CTs, Timeout-/Outputlimit-Test und Nachweis, dass alle echten
Updatepfade serverseitig deaktiviert bleiben. Beta.20-Tag und Produktivsysteme
werden dafür nicht verändert; der Kandidat gehört in eine nächste Beta.
