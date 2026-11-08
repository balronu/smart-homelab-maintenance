# Phase 34 – sichere automatische OS-/APT-Erkennung

## Implementiert

`agent/smart_homelab_maintenance/discovery_probe.py` definiert einen
side-effect-freien Probe-Vertrag:

- `discover_only` ruft niemals einen Transport auf und bleibt damit
  gastzugriffsfrei.
- Ein ausdrücklich aktivierter Transport liefert ausschließlich strukturierte
  Ergebnisse; der Aufrufer kann keine Shell- oder Pfadargumente übergeben.
- `os-release` wird nur für `ID` und `VERSION_ID` aus begrenzter Ausgabe
  gelesen. APT- und dpkg-Versionen müssen separat nachgewiesen werden.
- Zustände sind `pass`, `unsupported`, `unknown`, `stopped`, `unauthorized`
  und `probe_failed`.
- Fehler führen zu keinem automatischen Retry und zu keiner Autorisierung.

Der Transport ist absichtlich noch nicht mit dem produktiven Root-Helper
verdrahtet. Dafür braucht es einen separaten, geprüften Discovery-Socket oder
eine Erweiterung des Helper-Protokolls mit eigener Berechtigung. Der bestehende
`read`-/`simulate`-Helper darf nicht stillschweigend zu einem Discovery- oder
Shell-Runner werden.

## Datenfluss

1. Proxmox liefert dynamisch alle LXC-/VM-Inventarobjekte.
2. Nur LXC-Records mit laufendem Status können eine Probe erhalten.
3. Eine Probe ist nur mit explizit aktivierter Discovery-Berechtigung zulässig.
4. Ein erfolgreicher Debian-/Ubuntu-/APT-Nachweis wird an die Policy-Planung
   aus PR #55 übergeben.
5. `discover_only` bleibt Standard; der Auto-Modus entscheidet erst danach,
   ob ein konkreter numerischer CTID-Kandidat autorisiert werden darf.
6. Gestoppte, entfernte, unbekannte oder nicht unterstützte Ziele werden
   entzogen bzw. als Kandidat blockiert. VMs bleiben außerhalb des Pfads.

## Noch offen

- fester root-owned Discovery-Transport mit eigener Allowlist-/Policy-Grenze;
- atomare Speicherung von Probe-Provenienz und Generation;
- API-/HA-Anzeige der sechs Zustände;
- End-to-End-Fixtures für Debian 12/13, Ubuntu, Fehler, Timeout, Outputlimit
  und konkurrierende Probes.

Produktive Probes, Helper-Aktivierung, Simulationen und Änderungen an `pve-home`
sind in dieser Phase nicht enthalten.
