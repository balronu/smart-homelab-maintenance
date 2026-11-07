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
4. Nach dem Stopp muss die Unit inaktiv sein. `LISTEN` sowie alle aktiven
   TCP-Zustände blockieren den Austausch; der kernelverwaltete Endzustand
   `TIME-WAIT` wird ausgenommen, weil er keinen Listener-Prozess besitzt und
   mit `SO_REUSEADDR` keinen neuen Server-Bind verhindern soll. Ein reiner
   Listener-Check würde dagegen einen Übergangszustand zwischen Stopp und
   neuem Bind-Versuch übersehen. Bleibt der Dienst oder ein blockierender
   TCP-Zustand bestehen, wird der Austausch nicht begonnen und keine zweite
   Instanz gestartet.
5. Der Agent-Code wird atomar ausgetauscht; Konfiguration, TLS-Dateien,
   Credentials und Firewall-Skripte liegen außerhalb des ersetzten `agent/`-
   Baums.
6. Der Agent behandelt `SIGTERM`/`SIGINT` kontrolliert, beendet den
   Server-Loop und schließt den Listen-Socket. `SO_REUSEPORT` bleibt bewusst
   deaktiviert; zwei Agent-Instanzen können daher nicht parallel lauschen.
7. Nach dem Start wartet der Updater höchstens 30 Sekunden mit begrenzten
   Versuchen auf einen TLS-validierten Healthcheck.
8. Der Updater erfasst vor dem Stopp den systemd-Restartzähler. Jeder Anstieg
   während der Readiness gilt als fehlgeschlagener Start, auch wenn ein
   späterer automatischer `Restart=on-failure`-Versuch gesund antwortet. So
   kann ein Upgrade nach wiederholten Bind-Fehlern nicht fälschlich mit Exit 0
   enden.
9. Der Healthcheck muss Schema 1, Status `ok`, API-Vertrag 1.1 und exakt die
   erwartete Agent-Version melden.
10. Bei einem Timeout, einer inkompatiblen Antwort, einem Dienstfehler oder
   einem systemd-Restart wird
   der Dienst gestoppt, ein systemd-Fehlerzustand zurückgesetzt und der
   vorherige Agent-Code wiederhergestellt.
11. Der Rollback-Code wird erneut mit demselben TLS-/API-Healthcheck geprüft.
   Scheitert auch dieser Check, bleibt der Dienst gestoppt und der Updater
   liefert einen eindeutigen Rollback-Fehlercode.

## Forensikdaten

Der Updater schreibt an den Übergängen `vor-stop`, `nach-stop`, `vor-swap` und
`nach-start` nur nicht-sensitive Diagnosewerte: systemd MainPID/ControlPID,
ControlGroup, Cgroup-Prozesse sowie `ss -Htanp` für Port 48128. Diese Daten
ermöglichen die Zuordnung eines künftigen Bind-Fehlers. Historische PID- oder
Socket-Zuordnungen, die nicht im Journal erfasst wurden, können nachträglich
nicht rekonstruiert werden und dürfen nicht als bewiesen ausgegeben werden.

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
