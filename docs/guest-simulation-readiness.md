# Gast-Simulationsbereitschaft / Guest simulation readiness

## Sicherheitsvertrag

Die aktuelle Entwicklung bereitet ausschließlich **Paket-Simulationen** vor.
Sie führt keine Paketinstallation, Entfernung, Aktualisierung oder
Paketlistenaktualisierung aus. Es gibt keinen frei übergebenen Shell-Befehl,
keinen generischen Runner und keinen automatischen Start gestoppter Gäste.

The current development only prepares **package simulations**. It never
installs, removes, upgrades, or refreshes package indexes. No shell command is
accepted from the frontend, and stopped guests are never started.

| Zieltyp | Transport | Voraussetzungen | Entwicklungsstatus |
|---|---|---|---|
| Host | lokaler fester APT-Lese-/Simulationspfad | frischer Check, API- und Sicherheitsprüfungen | geeignet, wenn Backend `dry_run_supported=true` liefert |
| LXC | ausschließlich geprüfter LXC-APT-Helper | laufend, Debian/Ubuntu + APT nachgewiesen, explizite Ziel-Allowlist | vorbereitet, standardmäßig nicht autorisiert |
| VM | kein `pct exec`; separater Gasttransport erforderlich | unterstützte, ausdrücklich autorisierte Methode fehlt derzeit | `not_checked`, keine Simulation |
| gestoppter Gast | kein Start und kein Gastbefehl | Gast muss ausdrücklich laufen | `not_checked` |

The agent reports the method and reason in the update result. A VM is rejected
before any reader or runner is called, so a VM identifier can never be routed
through the LXC `pct exec` path. The permanent installation prohibition is
independent of simulation eligibility.

## Inventuraufnahme 2026-11-08

Die folgende Aufnahme wurde read-only auf `pve-home` erstellt; sie ist keine
Autorisierung und startet oder verändert keinen Gast:

- VMs: `104 haos` (running), `106 pbs` (running).
- LXCs: `101 cloudflared`, `102 zigbee2mqtt-haus`, `103 mariadb`,
  `105 OpenClaw`, `107 paperless-ngx`, `108 zigbee2mqtt-womo`, `109 mqtt`,
  `110 npm`, `111 pve-touch-dashboard` (running).
- LXC `112 stellantis-oauth-worker` ist `stopped` und wird nicht angesprochen.

Für diese Inventarantwort sind Gast-OS, Paketmanager und explizite
Autorisierungen nicht passiv nachgewiesen. Daher bleiben die LXC-Ziele ohne
separate Allowlist `unauthorized` bzw. `not_checked`; die VMs bleiben
`not_checked` wegen fehlendem Gasttransport.

## Authorization gate

Eine spätere Aktivierung muss pro numerischer Ziel-ID erfolgen und darf nur
OS-Name, Version und den festen Paketmanager `apt` enthalten. Helper, Socket
und Allowlist bleiben bis zu einer separaten Freigabe deaktiviert. Parallele
Simulationen desselben Ziels werden abgewiesen; Antworten sind zeit- und
ausgabebegrenzt.

## Beta.31 Kandidatenmatrix

Die konkrete LXC-/VM-Inventur, die festen Helper-Grenzen und die offenen
Autorisierungsschritte stehen in
[`beta31-simulation-readiness.md`](beta31-simulation-readiness.md). Sie ist
eine read-only Abnahmegrundlage; sie aktiviert keinen Helper. VMs bleiben
dort und im Backend dauerhaft von Paketprüfung und Simulation ausgeschlossen.
