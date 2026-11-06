# Phase 4.15 – Korrigierte Firewall-Persistenz aktivieren

## Ergebnis

Die korrigierte Persistenz wurde am 2026-11-06 erfolgreich auf `pve-home`
installiert und aktiviert. Die bereits vorhandenen Firewall-Regeln blieben
unverändert; es wurden keine Duplikate erzeugt.

Es erfolgte kein Proxmox-Neustart. Der Agent wurde nicht installiert und kein
TLS-/DNS-Schritt ausgeführt.

## 1. Vorprüfung

Alle verpflichtenden Vorprüfungen waren erfolgreich:

- geprüfter Commit `4ff3ca8` lokal verifiziert;
- lokale Regression: 37/37 Tests bestanden;
- aktives Backend weiterhin `iptables-legacy`/`ip6tables-legacy`;
- Proxmox-Firewall-Konfiguration nicht aktiviert;
- Tailscale aktiv und bestehende Regel-Digest unverändert;
- IPv4-Allowlist und IPv6-Sperre vorhanden;
- keine fremden Chains betroffen;
- Port 48128 nicht belegt;
- SSH, Proxmox API und Wartungsdienst erreichbar;
- Zielpfade für Unit, Skripte und Konfiguration vor Installation frei;
- Remote-Dry-Run mit der realen `/32`-Darstellung erfolgreich.

## 2. CIDR-Korrektur

Die reale `iptables-save`-Ausgabe mit `/32` wurde erfolgreich akzeptiert.
Einzeladressen werden semantisch verglichen. Breitere Netze, ungültige Werte,
Duplikate und falsche Allow/Drop-Reihenfolge würden weiterhin blockiert.

## 3. Installation und Aktivierung

Installiert wurden ausschließlich:

- `/usr/local/sbin/agent-firewall-common.sh` – `0755`;
- `/usr/local/sbin/apply-agent-firewall.sh` – `0755`;
- `/usr/local/sbin/remove-agent-firewall.sh` – `0755`;
- `/etc/systemd/system/smart-homelab-maintenance-firewall.service` – `0644`;
- `/etc/smart-homelab-maintenance/firewall.conf` – `0600`.

Die Unit wurde mit `systemd-analyze verify`, `systemctl daemon-reload` und
`systemctl enable --now` aktiviert.

Read-back:

- Unit: `enabled`;
- ActiveState: `active`;
- SubState: `exited`;
- Result: `success`;
- ExecMainStatus: `0`.

Die Unit wartet auf `network-online.target` und `tailscaled.service` und zieht
beide Units über `Wants` mit.

## 4. Firewall-Regeln vor und nach Aktivierung

Vorher und nachher identisch:

```text
IPv4: konfigurierte HA-VM-104-Einzeladresse -> konfigurierte Agent-Hostadresse,
      TCP 48128 -> ACCEPT
IPv4: anderer TCP-Verkehr zu 48128 -> DROP
IPv6: TCP 48128 -> DROP
```

Die eigene INPUT-Sprungregel steht weiterhin an Position 1 vor dem Tailscale-
Sprung. Zählerprüfung:

- IPv4-Sprung: 1;
- IPv4-Allow: 1;
- IPv4-Drop: 1;
- IPv6-Sprung: 1;
- IPv6-Drop: 1.

Damit wurden keine Regeln dupliziert, gelöscht oder umsortiert.

## 5. Bestehende Dienste

| Prüfung | Ergebnis |
|---|---|
| SSH-Sitzung | PASSED |
| Proxmox API/HTTPS 8006 | PASSED – HTTP 401 |
| Alter Wartungsdienst 8128 | PASSED – HTTP 200 |
| Tailscale | PASSED – aktiv |
| TCP 48128 | kein Listener |
| Proxmox-Firewall | nicht aktiviert |

Das Journal enthält den alten, bereits dokumentierten Fehlversuch aus Phase
4.13. Der aktuelle Unit-Start nach der Korrektur endete erfolgreich und ohne
neuen Fehler.

Bei der systemd-Prüfung wurde außerdem ein bereits bestehender, unabhängiger
`srv-nvr-recordings`-Ordering-Cycle gemeldet. Er wurde nicht verändert und
beeinträchtigt den erfolgreichen Start der Agent-Firewall-Unit nicht.

## 6. Rücknahmebereitschaft

Das Rücknahmeskript ist weiterhin unter `/usr/local/sbin/remove-agent-firewall.sh`
vorhanden und verwaltet ausschließlich die markierten eigenen Chains und
Sprünge. Die systemd-Unit kann separat deaktiviert werden:

```text
systemctl disable --now smart-homelab-maintenance-firewall.service
/usr/local/sbin/remove-agent-firewall.sh \
  --config /etc/smart-homelab-maintenance/firewall.conf \
  --apply --confirm
```

Ein globales Firewall-Flush ist nicht erforderlich und nicht vorgesehen.

## 7. Offene Prüfungen und Entscheidung

Die Wiederherstellung nach einem echten Proxmox-Neustart wurde ausdrücklich
nicht praktisch getestet. Der Agent lauscht noch nicht auf 48128; deshalb
ist die Ende-zu-Ende-Paketwirkung weiterhin nicht vollständig verifiziert.

**GO für die aktivierte Firewall-Persistenz ohne Neustart.**

**NO-GO für TLS-/DNS-Einrichtung und Agentbetrieb**, bis diese Schritte separat
freigegeben und getestet werden.
