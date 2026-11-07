# Agent-Updater: Readiness und Rollback

## Zweck

Der Beta.19-Agent-Updateversuch hat gezeigt, dass ein Dienst nach einem
kontrollierten Stopp kurzzeitig noch nicht bindbereit sein kann. Ein einzelner
Healthcheck direkt nach `systemctl start` ist deshalb kein ausreichender
Readiness-Nachweis.

## Sicherheitsverhalten

`scripts/upgrade-agent.sh` bleibt standardmäßig eine Vorprüfung. Der
schreibende Pfad benötigt weiterhin ausdrücklich `--apply --confirm`.

Bei einem freigegebenen Update gilt:

1. Quelle, Commit, Dienst, Zielpfad und CA werden geprüft.
2. Die zuvor installierte Agent-Version wird erfasst.
3. Nur `smart-homelab-maintenance-agent.service` wird gestoppt.
4. Nach dem Stopp muss Port 48128 tatsächlich frei sein. Bleibt ein Listener
   bestehen, wird der Austausch nicht begonnen und der Dienst wird nicht mit
   einer zweiten Instanz überlagert.
5. Der Agent-Code wird atomar ausgetauscht; Konfiguration, TLS-Dateien,
   Credentials und Firewall-Skripte liegen außerhalb des ersetzten `agent/`-
   Baums.
6. Der Agent behandelt `SIGTERM`/`SIGINT` kontrolliert, beendet den
   Server-Loop und schließt den Listen-Socket. `SO_REUSEPORT` bleibt bewusst
   deaktiviert; zwei Agent-Instanzen können daher nicht parallel lauschen.
7. Nach dem Start wartet der Updater höchstens 30 Sekunden mit begrenzten
   Versuchen auf einen TLS-validierten Healthcheck.
8. Der Healthcheck muss Schema 1, Status `ok`, API-Vertrag 1.1 und exakt die
   erwartete Agent-Version melden.
9. Bei einem Timeout, einer inkompatiblen Antwort oder einem Dienstfehler wird
   der Dienst gestoppt, ein systemd-Fehlerzustand zurückgesetzt und der
   vorherige Agent-Code wiederhergestellt.
10. Der Rollback-Code wird erneut mit demselben TLS-/API-Healthcheck geprüft.
   Scheitert auch dieser Check, bleibt der Dienst gestoppt und der Updater
   liefert einen eindeutigen Rollback-Fehlercode.

## Staging-Regeln

Vorhandenes `agent.previous.*.staging` blockiert einen neuen Updateversuch und
erfordert eine manuelle Prüfung. Der Updater löscht weder vorhandenes Staging
noch den fehlerhaften Code automatisch. Nach einem erfolgreichen Austausch
bleibt der vorherige Code als manueller Rückfallstand erhalten; die spätere
Bereinigung ist ein separater, ausdrücklich zu prüfender Vorgang.

## Fehlercodes

- `72`: begrenztes Readiness-Fenster abgelaufen oder Healthcheck inkompatibel.
- `73`: Rollback konnte nicht sicher abgeschlossen werden.

Andere Vorprüfungsfehler liefern den normalen Fehlercode `1`. Der Updater
startet keine unbegrenzte eigene Retry-Schleife. Eine systemd-Unit mit
`Restart=on-failure` wird bei Ablauf des Readiness-Fensters vom Updater
gestoppt, bevor der Rollback beginnt.

## Grenzen

Der Mechanismus aktualisiert keine Home-Assistant-Installation, keine
Proxmox-Komponenten, keine VMs/LXCs, keine Paketlisten und keine Firewall.
Echte Systemupdates bleiben serverseitig gesperrt.
