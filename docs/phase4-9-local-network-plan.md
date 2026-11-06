# Phase 4.9 – Lokaler Netzwerkplan für den Agenten

## Prüfgrenzen

Die Prüfung erfolgte am 2026-11-06 ausschließlich lesend. Es wurden keine
Firewallregeln, DNS-Einträge, Zertifikate, Tokens, Dienste oder VM-104-
Einstellungen verändert.

Private IP-Adressen und interne Hostnamen werden bewusst nicht in diese
versionierte, später veröffentlichbare Projektdokumentation aufgenommen. Die
exakten Live-Werte wurden im kontrollierten Betreiberkontext geprüft und sind
für die unten markierten Platzhalter einzusetzen.

## 1. Tatsächliche Netzwerkstruktur

| Element | Live-Befund |
|---|---|
| Proxmox-Management | `vmbr0`, privates `/24`, Hostadresse vorhanden |
| VM 104 | `haos`, direkt an `vmbr0`, private IPv4-Adresse vorhanden |
| Layer-2-Pfad | VM 104 und Host teilen dieselbe Bridge und dasselbe Subnetz |
| Bridge-VLAN | kein VLAN-Filtering auf `vmbr0` nachgewiesen |
| Agent-Port | TCP 48128 aktuell nicht belegt |
| Alter Dienst | TCP 8128 aktiv; bleibt unverändert |
| Proxmox-Web/API | TCP 8006 aktiv; bleibt unverändert |
| DNS | interner Knotename löst lokal; kein Agent-DNS-Eintrag nachgewiesen |

Die exakten Werte für `<HOST_IP>` und `<VM104_IP>` wurden live aus der
Proxmox-Adresse und dem QEMU-Gastagenten ermittelt. Sie werden nicht in der
öffentlichen Repository-Historie gespeichert.

## 2. Aktuelle Firewall-Wirksamkeit

Die Proxmox-Firewall meldet `disabled`. Die Hostfilterung enthält derzeit
Tailscale-spezifische iptables-Ketten, aber keine Regel für TCP 48128. Die
iptables-Policies sind für den normalen INPUT-/FORWARD-Pfad nicht als enge
Agent-Allowlist konfiguriert.

Daraus folgt:

**Der Port wäre bei einer späteren Bindung an die Bridge aktuell nicht auf VM
104 begrenzt.** TLS und Bearer-Token wären Anwendungsschutz, aber kein
Quellnetzschutz.

## 3. Empfohlene eng begrenzte Regel

Die folgende Regelplanung betrifft ausschließlich TCP 48128 zu `<HOST_IP>`.
Sie verändert weder SSH, Proxmox-Web/API auf 8006 noch den alten Dienst auf
8128. Administrationsquellen sind absichtlich noch nicht eingetragen; sie
benötigen eine separate Freigabe.

```text
iptables -N SHM_AGENT
iptables -A SHM_AGENT -p tcp -s <VM104_IP> -d <HOST_IP> --dport 48128 -j ACCEPT
iptables -A SHM_AGENT -p tcp -d <HOST_IP> --dport 48128 -j DROP
iptables -I INPUT 1 -p tcp -d <HOST_IP> --dport 48128 -j SHM_AGENT
```

Die Einfügung an Position 1 ist wichtig, damit vorhandene generische oder
Tailscale-bezogene Sprünge die Agent-Regel nicht umgehen. Für eine dauerhafte
Bereitstellung muss die Regel in den freigegebenen Host-/Proxmox-
Persistenzmechanismus überführt werden; ein flüchtiger manueller iptables-
Eintrag genügt nicht.

**Parser-Nachweis:** Die Regelstruktur wurde mit `iptables-restore --test`
gegen die aktuellen Live-Adressen syntaktisch geprüft. Der Test lädt keine
Regel und verändert den Host nicht. Eine tatsächliche Paketprüfung ist erst
nach Installation eines Testlisteners und ausdrücklicher Firewallfreigabe
zulässig.

## 4. Änderungs- und Rücknahmeplan

Vor einer Änderung:

1. aktuelle iptables-/Persistenzkonfiguration exportieren und von einem
   Operator prüfen lassen;
2. den Agenten noch nicht starten;
3. nur TCP 48128 und nur die VM-104-Quelle freigeben;
4. die Regelreihenfolge und den unveränderten Status von 8006/8128 prüfen.

Rücknahme:

```text
iptables -D INPUT -p tcp -d <HOST_IP> --dport 48128 -j SHM_AGENT
iptables -F SHM_AGENT
iptables -X SHM_AGENT
```

Die echten Rücknahmebefehle müssen vor Ausführung gegen die tatsächlich
installierten Regelzähler und Kommentare geprüft werden. Kein pauschales
Flushen von INPUT, FORWARD oder der Tailscale-Ketten ist zulässig.

## 5. TLS und DNS

Empfohlen ist ein dedizierter privater DNS-Name, der ausschließlich intern auf
`<HOST_IP>` zeigt, sowie ein eigenes Agent-Zertifikat mit diesem Namen im SAN.
Das Proxmox-Webzertifikat und sein Schlüssel werden nicht wiederverwendet.

Eine private CA ist nur geeignet, wenn die Vertrauenskette in HAOS tatsächlich
vorhanden ist. Die aktuelle Integration hat zwar TLS-Prüfung, aber keinen
freigegebenen produktiven CA-Installationspfad im Config Flow. Vor der
Verbindung muss daher entweder die HAOS-Vertrauenskette nachgewiesen oder die
Integration um einen geprüften CA-Pfad erweitert werden.

Cloudflare Tunnel ist ausgeschlossen, weil er öffentliche NPM-Routen bedient.
Tailscale ist erst geeignet, wenn VM 104 als erreichbarer Peer aufgenommen und
eine enge ACL nachgewiesen wurde. Der direkte private Bridge-Pfad ist daher
der einfachste Kandidat, aber ohne Host-Allowlist noch nicht sicher genug.

## 6. Noch notwendige Freigaben

- Freigabe der konkreten VM-104-Quelladresse und optionaler Adminquellen;
- Freigabe für genau eine dauerhafte Hostfilter-Technik;
- Freigabe des privaten DNS-Namens und der CA-/Zertifikatsbereitstellung;
- Nachweis der HAOS-TLS-Vertrauenskette;
- anschließender Dry-Run und separat freigegebener Installationstest.

## 7. Entscheidung

**NO-GO für Netzwerkänderung und Agentbereitstellung.**

Die private L2-Struktur und ein freier Port sind vorhanden, aber die aktuelle
Firewall schützt den Agenten noch nicht. Der nächste Schritt ist eine
separat freigegebene, reversible Allowlist-Änderung auf ausschließlich TCP
48128; bis dahin bleiben DNS, Firewall, TLS, Tokens und Dienste unverändert.
