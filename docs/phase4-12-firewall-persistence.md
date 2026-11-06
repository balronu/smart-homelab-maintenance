# Phase 4.12 – Firewall-Persistenz prüfen

## Ergebnis und Grenzen

Die Prüfung erfolgte am 2026-11-06 ausschließlich lesend und in isolierten
Testumgebungen. Die systemd-Unit wurde auf dem Proxmox-Host nicht installiert,
nicht aktiviert und nicht gestartet. Es gab keinen Neustart und keine Änderung
an Agent, DNS, TLS oder VM 104.

**Entscheidung: NO-GO für die produktive Persistenzaktivierung.**

Die Vorlage ist für einen späteren, separat freizugebenden kontrollierten Test
geeignet. Vor dieser Freigabe muss der tatsächliche Boot-Read-back erfolgen.

## 1. Aktueller Regelzustand

Der Live-Zustand entspricht Phase 4.11:

- `iptables-legacy` und `ip6tables-legacy` sind aktiv;
- die eigenen Chains `SHM_AGENT_48128_V4` und `SHM_AGENT_48128_V6` existieren;
- der eigene INPUT-Sprung steht jeweils an Position 1;
- die IPv4-Allow-Regel, IPv4-Drop-Regel und IPv6-Drop-Regel sind vorhanden;
- der Proxmox-Firewallstatus ist nicht aktiviert;
- Tailscale-Chains und Tailscale-Dienst sind unverändert aktiv;
- nftables hat keine aktiven Tabellen und sein Dienst ist inaktiv;
- die Persistenz-Unit ist nicht installiert, nicht aktiviert und nicht aktiv.

Die Prüfung erfolgte über `iptables -S`, `ip6tables -S`,
`pvesh get /cluster/firewall/options`, `systemctl`, `nft list tables` und
`iptables-save`/`ip6tables-save`.

## 2. Prüfung der systemd-Vorlage

Datei:

`deploy/systemd/smart-homelab-maintenance-firewall.service.example`

Bewertung:

- `Type=oneshot` mit `RemainAfterExit=yes` ist für einmaliges Regelsetzen
  passend;
- `After=network-online.target tailscaled.service` verhindert eine Ausführung
  vor den genannten Units, sofern diese gestartet werden;
- `Wants=network-online.target tailscaled.service` zieht die benötigten Units
  beim späteren Aktivieren mit;
- `ConditionPathExists` verhindert einen Start ohne lokales Skript oder ohne
  lokale Konfiguration;
- `ExecStart` verwendet das Apply-Skript ausschließlich mit `--apply --confirm`;
- die Vorlage verändert keine Standard-Policies und lädt keinen vollständigen
  Regelsatz;
- die Konfiguration muss außerhalb des Repositories geschützt bereitgestellt
  werden und darf keine Secrets oder unmaskierten Zugangsdaten enthalten.

Eine isolierte `systemd-analyze verify`-Prüfung mit temporärem Root und
Fixture-Units war erfolgreich. Eine direkte Host-Installation zur Prüfung der
Unit wurde bewusst nicht durchgeführt.

## 3. Idempotenz und sichere Verwaltung

Das Apply-Skript:

- erkennt das geprüfte `iptables-legacy`-Backend;
- prüft die Proxmox-Firewall vor jeder Änderung;
- verwendet nur die eindeutig benannten eigenen Chains;
- prüft vorhandene markierte Regeln und ergänzt nur fehlende Regeln;
- verweigert unmarkierte oder abweichende Regeln in den eigenen Chains;
- setzt keine vollständigen Regeln mit `iptables-restore`;
- führt keinen globalen Flush von INPUT, FORWARD oder Tailscale aus.

Das Rücknahmeskript entfernt ausschließlich die markierten eigenen Sprünge,
leert danach nur die eigenen Chains und löscht nur diese Chains.

## 4. Isolierte Wiederherstellungssimulation

Mit Fake-Binaries für `iptables`, `ip6tables`, `iptables-save`,
`ip6tables-save`, `pvesh` und `ip` wurde der spätere ExecStart simuliert.

Ergebnis:

- Apply mit `--apply --confirm`: **PASSED**;
- IPv4- und IPv6-Sprungregeln wurden geplant: **PASSED**;
- eigene Chains wurden geplant: **PASSED**;
- kein `iptables-restore`/`ip6tables-restore`: **PASSED**;
- kein globales Flush fremder Chains: **PASSED**;
- Shell-Syntax: **PASSED**;
- bestehende lokale Regression: **33/33 PASSED**.

## 5. Vorgesehene spätere Installation

Diese Befehle wurden nicht ausgeführt. Vor Ausführung ist eine gesonderte
Freigabe mit Zweitzugang oder lokaler Konsole erforderlich:

```text
install -m 0755 scripts/agent-firewall-common.sh /usr/local/sbin/agent-firewall-common.sh
install -m 0755 scripts/apply-agent-firewall.sh /usr/local/sbin/apply-agent-firewall.sh
install -m 0755 scripts/remove-agent-firewall.sh /usr/local/sbin/remove-agent-firewall.sh
install -d -m 0750 /etc/smart-homelab-maintenance
# lokale, geheimnisfreie HOST_IP/HA_IP/INTERFACE-Konfiguration mit 0600 ablegen
install -m 0644 deploy/systemd/smart-homelab-maintenance-firewall.service.example \
  /etc/systemd/system/smart-homelab-maintenance-firewall.service
systemctl daemon-reload
systemctl enable --now smart-homelab-maintenance-firewall.service
```

Nach der Aktivierung müssen `systemctl status`, `iptables -S`, `ip6tables -S`
und die Tailscale-Chains gelesen werden. Erst danach wäre ein Neustart in einem
separat freigegebenen Wartungsfenster zulässig.

## 6. Rücknahme

Bei unerwarteten Auswirkungen zunächst die bestehende Verwaltungssitzung offen
halten und anschließend ausschließlich das vorbereitete Skript verwenden:

```text
systemctl disable --now smart-homelab-maintenance-firewall.service
/usr/local/sbin/remove-agent-firewall.sh \
  --config /etc/smart-homelab-maintenance/firewall.conf \
  --apply --confirm
systemctl daemon-reload
```

Danach müssen SSH, Proxmox-Web/API, der alte Wartungsdienst und Tailscale
erneut read-back-geprüft werden. Die Unit- und Skriptdateien dürfen erst nach
diesem Read-back entfernt werden. Es gibt keinen globalen Firewall-Flush.

## 7. Spätere Filterwirkungsprüfung

Da aktuell kein Agent auf TCP 48128 lauscht, kann die echte Allow-/Drop-Wirkung
erst nach separater Agent- und Testfreigabe geprüft werden. Der spätere Test
muss mindestens enthalten:

1. erlaubte Verbindung von VM 104;
2. blockierte Verbindung von einer unabhängigen Quelle;
3. IPv6-Verbindungsversuch;
4. Read-back der Paket- und Bytezähler;
5. Prüfung von SSH, Port 8006, Port 8128 und Tailscale.

Bis dahin bleibt die Ende-zu-Ende-Filterwirkung als **nicht vollständig
verifiziert** gekennzeichnet.
