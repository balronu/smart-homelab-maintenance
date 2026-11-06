# Phase 4.10 – Firewall-Schutz für TCP 48128

## Ergebnis und Grenzen

Die Vorbereitung erfolgte am 2026-11-06 ausschließlich lesend und in einer
isolierten Testumgebung. Keine Firewallregel wurde produktiv angewendet, kein
Firewall-Dienst aktiviert, kein Dienst gestartet und kein bestehender Dienst
verändert.

Die exakten privaten IP-Adressen aus dem Betreiberauftrag werden nicht erneut
in die versionierte Projekthistorie geschrieben. Die Skripte verlangen sie
explizit über eine lokale, nicht veröffentlichte Konfigurationsdatei.

## 1. Aktive Paketfiltertechnik

Live-Befund auf dem Proxmox-Host:

- `/usr/sbin/iptables` ist `iptables-legacy` 1.8.x;
- `iptables-nft` ist nur als Alternative installiert und wird nicht verwendet;
- keine aktiven nftables-Tabellen und kein aktiver nftables-Dienst;
- `pve-firewall`-Unit läuft, aber die Proxmox-Firewall-Konfiguration weist
  keine aktivierte Cluster-/Node-Allowlist auf;
- keine erkannte `iptables-persistent`-/`netfilter-persistent`-Installation;
- vorhandene iptables-Regeln stammen im Filterpfad im Wesentlichen aus
  Tailscale (`ts-input`/`ts-forward`) und dürfen nicht verändert werden.

Damit wäre eine generische Regel in INPUT ohne definierte Position nicht
sicher genug: Der bestehende Tailscale-Sprung steht bereits im INPUT-Pfad.
Die geplante eigene Sprungregel wird deshalb mit `-I INPUT 1` vor vorhandenen
Sprüngen eingefügt, bleibt aber standardmäßig nur ein Dry-Run.

## 2. Implementierte Regelstrategie

Die Skripte verwenden zwei eindeutig benannte Chains:

```text
SHM_AGENT_48128_V4
SHM_AGENT_48128_V6
```

IPv4:

```text
TCP 48128 von VM 104 zur Proxmox-Agent-Adresse -> ACCEPT
TCP 48128 alle anderen Quellen/Ziele -> DROP
```

IPv6:

```text
TCP 48128 -> DROP
```

Damit wird ein später versehentliches IPv6-Binding nicht ungeschützt
erreichbar. SSH, Proxmox-Web/API und Port 8128 werden nicht adressiert.

Jede eigene Regel erhält eindeutige Kommentare. Die Skripte verweigern:

- unbekannte oder nicht-legacy Paketfilter-Backends;
- nicht prüfbaren Proxmox-Firewallstatus;
- aktivierte Proxmox-Firewall-Konfiguration;
- abweichende oder unmarkierte Regeln in den eigenen Chains;
- Apply ohne die zusätzliche Bestätigung `--confirm`.

## 3. Skripte und Befehle

Vorbereitung:

```text
deploy/firewall-agent.conf.example -> lokale Datei außerhalb des Repositories
```

Die lokale Datei enthält ausschließlich:

```text
HOST_IP=<PROXMOX_AGENT_BIND_IPV4>
HA_IP=<HOME_ASSISTANT_VM104_IPV4>
INTERFACE=vmbr0
```

Dry-Run, Standard und ausdrücklich wiederholbar:

```text
sudo scripts/apply-agent-firewall.sh \
  --config /etc/smart-homelab-maintenance/firewall.conf \
  --dry-run
```

Ein späterer, separat freizugebender Apply-Schritt wäre:

```text
sudo scripts/apply-agent-firewall.sh \
  --config /etc/smart-homelab-maintenance/firewall.conf \
  --apply --confirm
```

Die Rücknahme verwaltet ausschließlich die eigenen markierten Regeln:

```text
sudo scripts/remove-agent-firewall.sh \
  --config /etc/smart-homelab-maintenance/firewall.conf \
  --dry-run
sudo scripts/remove-agent-firewall.sh \
  --config /etc/smart-homelab-maintenance/firewall.conf \
  --apply --confirm
```

Es gibt kein pauschales Flush von INPUT, FORWARD, Tailscale oder anderen
Chains. Die Skripte sind idempotent, solange ihre eigenen Chains unverändert
bleiben; bei fremden Regeln mit denselben Chain-Namen stoppen sie.

## 4. Persistenz

Da derzeit kein persistenter iptables-Manager vorhanden ist, wurde eine
optionale systemd-Vorlage vorbereitet:

`deploy/systemd/smart-homelab-maintenance-firewall.service.example`

Sie läuft erst nach Netzwerk und Tailscale, lädt die lokale Konfiguration und
ruft das eigene Apply-Skript auf. Sie ist nicht installiert, nicht aktiviert
und nicht gestartet. Vor einer späteren Aktivierung muss geprüft werden, ob
Tailscale-Regeländerungen nach dem Start die Reihenfolge erneut verändern.
Nach einem kontrollierten Test muss der Dienststatus und die Regelposition
read-back geprüft werden.

Eine Aufnahme in Proxmox-Firewallregeln wurde bewusst nicht vorbereitet, weil
deren Aktivierung eine separate Proxmox-Freigabe und eine vollständige
Cluster-/Node-Firewallprüfung erfordern würde.

## 5. Lockout-Schutz

- Dry-Run ist Standard.
- Apply benötigt `--apply --confirm`.
- Die Regel betrifft ausschließlich TCP 48128.
- SSH, Port 8006 und Port 8128 werden nicht verändert.
- Vor Apply müssen SSH-Zweitzugang oder lokale Konsole, aktuelle Regel-
  sicherung und die Rücknahmeprozedur bereitstehen.
- Nach Apply muss zuerst die Regelreihenfolge geprüft werden; erst danach darf
  ein Agent gestartet und die Verbindung von VM 104 getestet werden.

## 6. Isolierte Tests

| Prüfung | Ergebnis |
|---|---|
| Shell-Syntax aller Firewallskripte | PASSED |
| Dry-Run mit gefälschten iptables-/pvesh-/ip-Binaries | PASSED |
| IPv4- und IPv6-Planung | PASSED |
| Apply-Bestätigungspflicht | PASSED |
| Konfigurationsdatei ohne Shell-Auswertung | PASSED |
| 30 bestehende Core-Tests | PASSED |
| Produktive Regelanwendung | NOT RUN – verboten |
| Persistenzaktivierung | NOT RUN – verboten |

Gesamt lokal: **33 Tests bestanden** (30 Core, 3 Firewall-Skript-Tests).

## 7. Risiken und Entscheidung

Verbleibende Risiken sind die Wechselwirkung mit Tailscale-Regelupdates, die
fehlende persistente Filterverwaltung und die noch nicht freigegebene
Agent-Bind-/TLS-Konfiguration. Diese Risiken werden durch die Backendprüfung,
eindeutige Chains, Dry-Run, Apply-Bestätigung und Lockout-Schutz begrenzt,
aber nicht durch diesen Schritt vollständig beseitigt.

**NO-GO für produktive Firewalländerung.**

Der nächste Schritt ist eine ausdrückliche Freigabe für einen kontrollierten
Apply-Test mit lokaler Konsole/Zweitzugang und anschließendem Read-back. Bis
dahin bleiben Firewall, Dienste, Agent und VM 104 unverändert.
