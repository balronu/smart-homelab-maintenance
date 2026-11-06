# Phase 4.11 – Kontrollierte Firewall-Aktivierung

## Ergebnis

Die vorbereitete Allowlist wurde am 2026-11-06 einmalig auf dem Proxmox-Host
angewendet. Die Aktivierung erfolgte ausschließlich mit dem geprüften Skript
aus Phase 4.10 und `--apply --confirm`.

Die systemd-Persistenz wurde **nicht** installiert, aktiviert oder gestartet.
Der Agent wurde nicht installiert und auf TCP 48128 lauscht weiterhin kein
Dienst.

Private Live-Adressen werden in dieser versionierten Dokumentation nicht
wiederholt. Sie wurden beim Apply explizit als lokale Parameter geprüft und
entsprechen dem freigegebenen Betreiberauftrag.

## 1. Vorprüfung

| Prüfung | Ergebnis |
|---|---|
| Lokaler geprüfter Commit | PASSED – `1403f8d0ab8b1270c657dcfb3f34e6e5f10ca441` |
| Aktives Backend | PASSED – `iptables-legacy` / `ip6tables-legacy` |
| Proxmox-Version | PASSED – 9.2.0 |
| Hostadresse auf `vmbr0` | PASSED |
| HA-VM-104-Adresse | PASSED – über QEMU-Gastagent verifiziert |
| Port 48128 vor Apply frei | PASSED |
| Proxmox-Firewall-Konfiguration | PASSED – nicht aktiviert |
| Tailscale-Dienst und Regeln | PASSED – vorhanden, nicht verändert |
| nftables | PASSED – keine aktiven Tabellen, Dienst inaktiv |
| Remote-Dry-Run | PASSED – keine Mutation |
| Rücknahmeskript | PASSED – vorhanden und auf eigene Marker begrenzt |

## 2. Tatsächlich angewendete Regeln

Die Regeln wurden in den ausschließlich eigenen Chains `SHM_AGENT_48128_V4`
und `SHM_AGENT_48128_V6` angelegt. Die Sprünge stehen in beiden INPUT-Ketten
an Position 1, vor dem bestehenden Tailscale-Sprung.

Semantischer Read-back:

```text
IPv4: freigegebene HA-VM-104-Adresse -> freigegebene Proxmox-Agent-Adresse, TCP 48128 -> ACCEPT
IPv4: jeder andere TCP-Verkehr zu Port 48128 -> DROP
IPv6: TCP 48128 -> DROP
```

Jede Regel trägt den Marker `smart-homelab-maintenance-48128`; die Allow- und
Drop-Regeln haben zusätzlich eigene Marker. Es wurden keine Standard-Policies,
anderen Chains, Tailscale-Regeln oder vorhandenen Dienste verändert.

## 3. Unmittelbarer Read-back

Bestätigt:

- IPv4- und IPv6-Sprungregel existiert jeweils in INPUT an Position 1;
- IPv4-Allow-Regel und IPv4-Drop-Regel existieren in der erwarteten Reihenfolge;
- IPv6-Drop-Regel existiert;
- `iptables -C` und `ip6tables -C` für die Sprünge erfolgreich;
- Regelzähler stehen bei null, da kein Dienst auf 48128 lauscht;
- Port 48128 ist weiterhin `not-listening`.

## 4. Bestehende Dienste und Verbindungen

| Prüfung | Ergebnis |
|---|---|
| Aktuelle SSH-Sitzung | PASSED |
| Proxmox HTTPS/API auf 8006 | PASSED – HTTP 401, Dienst erreichbar |
| Alter Wartungsdienst auf 8128 | PASSED – HTTP 200 |
| Tailscale-Dienst | PASSED – aktiv |
| Tailscale-Regeln | PASSED – unverändert gelesen |
| Agent auf 48128 | NOT RUN – absichtlich nicht installiert/gestartet |

## 5. IPv4-/IPv6-Filterwirkung

Die Regelstruktur und Reihenfolge sind vollständig verifiziert. Eine echte
erlaubte TCP-Verbindung von VM 104 und eine blockierte Verbindung von einer
unabhängigen Quelle konnten nicht getestet werden, weil:

1. auf 48128 kein Listener läuft; und
2. keine geeignete unabhängige Testquelle für eine blockierte Verbindung
   freigegeben oder eingerichtet wurde.

Die Paketfilterwirkung ist deshalb **nicht vollständig Ende-zu-Ende
verifiziert**. Es wurde dafür weder ein Listener gestartet noch ein produktiver
Agent verändert.

## 6. Rücknahmebereitschaft

Das vorbereitete Rücknahmeskript entfernt ausschließlich die markierten
Sprungregeln und die beiden eindeutig benannten eigenen Chains. Es verwendet
keinen globalen Flush und verändert keine fremden Chains.

Bei unerwarteten Auswirkungen ist der freizugebende Rücknahmebefehl:

```text
sudo scripts/remove-agent-firewall.sh --config /etc/smart-homelab-maintenance/firewall.conf --apply --confirm
```

Vor einer solchen Ausführung müssen die lokalen Parameter erneut gegen den
aktuellen Hostzustand geprüft werden.

## 7. Persistenz und Entscheidung

Die optionale systemd-Persistenzvorlage wird nicht installiert und bleibt deaktiviert.
Vor einer späteren Aktivierung müssen insbesondere Boot-Reihenfolge,
Tailscale-Regelupdates und ein Read-back nach Neustart in einem separaten,
freigegebenen Schritt geprüft werden.

**GO für den aktuell einmalig angewendeten, begrenzten Firewall-Schutz.**

**NO-GO für Persistenzaktivierung und Ende-zu-Ende-Agententest** bis zur
separaten Freigabe von Agent, TLS/DNS, Listener und kontrollierter Testquelle.
