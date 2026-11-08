# Beta.31 Simulationsbereitschaft / Simulation readiness

Dieses Dokument beschreibt den Beta.31-Kandidaten. Es aktiviert keinen
produktiven Gastzugriff, installiert keinen Helper und verändert keine
Allowlist. Jede spätere Aktivierung benötigt eine separate Freigabe und einen
isolierten Nachweis.

## Sicherheitsarchitektur

- Der Host nutzt weiterhin ausschließlich den bestehenden festen
  APT-Dry-Run-Pfad.
- Ein LXC kann erst nach passivem Nachweis von Laufstatus, Debian/Ubuntu, APT
  und einer expliziten numerischen Ziel-Allowlist simuliert werden.
- Der optionale Root-Helper akzeptiert ausschließlich die festen Operationen
  `read` und `simulate`; er führt weder `apt update` noch Installation,
  Entfernung, Upgrade, Neustart oder freie Shell-Befehle aus.
- Pro Ziel gibt es höchstens eine laufende Simulation. Laufzeit und Ausgabe
  sind begrenzt; gestoppte Gäste werden niemals gestartet.
- VMs bleiben dauerhaft Monitoring-only. VM-IDs werden vor jedem Reader- oder
  Runner-Aufruf abgewiesen und erreichen weder `pct exec` noch einen anderen
  Paket-Runner. Die Installationsaktion bleibt für alle Zieltypen deaktiviert.

## LXC-Eignungsmatrix

Die folgende Matrix ist eine Inventur-/Kandidatenmatrix, keine Autorisierung.
Die Produktiv-Allowlist bleibt unverändert deaktiviert.

| CTID | Name | Zustand | Kandidatenmethode | Aktueller Status | Voraussetzung |
|---:|---|---|---|---|---|
| 101 | cloudflared | laufend | fester LXC-Helper | nicht autorisiert | OS/APT passiv nachweisen, danach explizite Allowlist |
| 102 | zigbee2mqtt-haus | laufend | fester LXC-Helper | nicht autorisiert | OS/APT passiv nachweisen, danach explizite Allowlist |
| 103 | mariadb | laufend | fester LXC-Helper | nicht autorisiert | OS/APT passiv nachweisen, danach explizite Allowlist |
| 105 | OpenClaw | laufend | fester LXC-Helper | nicht autorisiert | OS/APT passiv nachweisen, danach explizite Allowlist |
| 107 | paperless-ngx | laufend | fester LXC-Helper | nicht autorisiert | OS/APT passiv nachweisen, danach explizite Allowlist |
| 108 | zigbee2mqtt-womo | laufend | fester LXC-Helper | nicht autorisiert | OS/APT passiv nachweisen, danach explizite Allowlist |
| 109 | mqtt | laufend | fester LXC-Helper | nicht autorisiert | OS/APT passiv nachweisen, danach explizite Allowlist |
| 110 | npm | laufend | fester LXC-Helper | nicht autorisiert | OS/APT passiv nachweisen, danach explizite Allowlist |
| 111 | pve-touch-dashboard | laufend | fester LXC-Helper | nicht autorisiert | OS/APT passiv nachweisen, danach explizite Allowlist |
| 112 | stellantis-oauth-worker | gestoppt | keine Ausführung | nicht geprüft | bleibt gestoppt; keine automatische Aktivierung |

Die Laufzustände stammen aus der read-only Inventur vom 2026-11-08. Für die
LXC-Ziele sind OS, Paketmanager und Allowlist im produktiven System nicht als
Freigabe nachgewiesen. Deshalb ist die korrekte Anzeige derzeit
`unauthorized` bzw. `not_checked`.

## VM-Matrix

| VMID | Name | Zustand | Beta.31-Verhalten | Begründung |
|---:|---|---|---|---|
| 104 | Home Assistant OS | laufend | Monitoring-only, `not_checked` | HAOS hat keinen normalen Debian-APT-Pfad; kein APT erzwingen |
| 106 | Proxmox Backup Server | laufend | Monitoring-only, `not_checked` | Debian-basiert, aber kein verifizierter Gasttransport; kein QEMU-Agent/SSH einrichten |

Die Karten zeigen Name, Laufstatus und Ressourcen sowie den Hinweis, dass
Updates über das jeweilige Gastbetriebssystem durchgeführt werden. Beta.31
prüft keine VM-Pakete und führt keine VM-Simulation aus.

## Abnahme für eine spätere Aktivierung

Vor einer separaten Freigabe sind je LXC ein isolierter Helper-/Allowlist-Test,
eine frische passive Planprüfung, eine erfolgreiche Simulation, Timeout- und
Fehlerfälle sowie ein Nachweis ohne Installationspfad erforderlich. Für VMs
gibt es in Beta.31 keine Aktivierungsfreigabe; ein neuer Gasttransport wäre ein
separates Architekturprojekt.

The English contract is identical: host simulation remains read-only, LXC
simulation is opt-in per target and fixed-command only, VM package checks and
simulation are permanently out of scope, and real package installation is not
supported.
