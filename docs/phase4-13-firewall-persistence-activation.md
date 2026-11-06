# Phase 4.13 – Aktivierung der Firewall-Persistenz

## Ergebnis

Die einmalige Aktivierung wurde am 2026-11-06 begonnen, aber sicher
abgebrochen. Die systemd-Unit konnte nicht erfolgreich starten und wurde
anschließend vollständig zurückgenommen.

**Ergebnis: NO-GO für die Persistenzaktivierung.**

Die bereits vor Phase 4.13 aktiven Agent-Firewall-Regeln blieben unverändert
bestehen. Es wurde kein Neustart durchgeführt, kein Agent installiert und kein
anderer Dienst verändert.

## 1. Vorprüfung

Die Vorprüfung war erfolgreich:

- `iptables-legacy`/`ip6tables-legacy` unverändert aktiv;
- Proxmox-Firewall-Konfiguration nicht aktiviert;
- Tailscale aktiv, bestehende Regel-Digest unverändert;
- IPv4-/IPv6-Agent-Chains und INPUT-Sprünge entsprachen Phase 4.12;
- Port 48128 war nicht belegt;
- Proxmox API auf 8006 antwortete `401`;
- alter Wartungsdienst auf 8128 antwortete `200`;
- SSH-Sitzung war aktiv;
- alle Zielpfade für Unit, Skripte und Konfiguration waren vorab abwesend.

## 2. Ausgeführte Installation

Installiert wurden vorübergehend ausschließlich:

- die drei geprüften Firewall-Skripte unter `/usr/local/sbin`;
- die systemd-Unit unter `/etc/systemd/system`;
- die lokale Konfiguration unter `/etc/smart-homelab-maintenance`.

`systemd-analyze verify` war vor dem Aktivierungsversuch erfolgreich. Die Unit
wurde mit `systemctl daemon-reload` geladen und mit `systemctl enable --now`
aktiviert.

## 3. Technischer Fehler

Der Start schlug mit folgendem Fehler ab:

```text
ERROR: Abweichende eigene IPv4-Regel gefunden; manuell prüfen.
```

Ursache ist ein Fehler in der bestehenden Konfliktprüfung von
`agent-firewall-common.sh`: `iptables-save` stellt IPv4-Adressen als
`192.168.178.126/32` und `192.168.178.199/32` dar, während die Prüfung die
Adressen ohne CIDR-Suffix in der Regelzeile sucht. Dadurch wurde die bereits
korrekte eigene Allow-Regel fälschlich als abweichend erkannt.

Wichtig: Der Fehler trat vor jeder Regeländerung des Apply-Laufs auf. Die
aktiven Chains und Regeln waren nach dem fehlgeschlagenen Start unverändert.

## 4. Rücknahme

Gemäß Sicherheitsvorgabe wurden ausschließlich die neu installierten eigenen
Persistenzbestandteile zurückgenommen:

- Unit deaktiviert;
- systemd-Daemon neu geladen;
- Unit-Symlink entfernt;
- Unit-Datei, Skripte und lokale Konfiguration entfernt;
- systemd-Fehlerzustand für diese Unit zurückgesetzt.

Die bestehenden `SHM_AGENT_48128_V4`-/`SHM_AGENT_48128_V6`-Chains und ihre
INPUT-Sprünge wurden **nicht** entfernt.

## 5. Nachprüfung

| Prüfung | Ergebnis |
|---|---|
| Unit installiert/aktiviert | NEIN – vollständig zurückgenommen |
| IPv4-Agent-Regeln | unverändert vorhanden |
| IPv6-Agent-Regel | unverändert vorhanden |
| SSH-Sitzung | PASSED |
| Proxmox API 8006 | PASSED – HTTP 401 |
| Wartungsdienst 8128 | PASSED – HTTP 200 |
| Tailscale | PASSED – aktiv |
| Agent-Port 48128 | nicht belegt |
| Neustart | nicht durchgeführt |

## 6. Offene Korrektur

Vor einem erneuten Aktivierungsversuch muss die CIDR-Normalisierung der
Konfliktprüfung im Repository korrigiert und isoliert getestet werden.
Erforderlich sind mindestens Tests mit den tatsächlichen `/32`-Darstellungen
von `iptables-save`, ein erneuter vollständiger CI-Lauf und eine neue explizite
Freigabe für den produktiven Aktivierungsversuch.

Ein Retry wurde in dieser Phase nicht durchgeführt.

**NO-GO für die nächsten TLS-/DNS-Schritte**, bis die Persistenz korrekt
aktivierbar ist. Die bereits aktive, nicht persistente Firewall-Allowlist bleibt
unverändert bestehen.
