# Phase 32 – automatische Erkennung und Einrichtung

## Architekturprüfung

PR #54 enthält bereits eine read-only Proxmox-Inventur für LXC und QEMU/VM,
eine dauerhafte VM-Sperre sowie einen root-eigenen Helper mit festem `read`-
und `simulate`-Protokoll. Die API kann neue Inventarobjekte ohne Dashboard-
Änderung anzeigen. `execution_enabled=false` bleibt erzwungen.

Noch nicht vorhanden waren eine policy-gesteuerte Allowlist-Planung, ein
idempotenter offizieller Helper-Installer und ein HA-Onboarding für den
Helper-Status. Die bisherige `lxc_helper_enabled`-Option wird nur beim
Agent-Start gelesen; sie darf daher nicht durch eine laufende Konfiguration
oder einen stillen Rechtewechsel ersetzt werden.

## Sicherheitsmodell

Die neue Planungslogik in `authorization.py` ist absichtlich ohne Seiteneffekt:

- `discover_only` erkennt alle Inventarobjekte, autorisiert aber keine neuen
  Gäste.
- `auto_authorize_supported_running` ist ein ausdrücklich wählbarer Modus und
  plant nur laufende LXCs mit positivem Debian-/Ubuntu-/APT-Nachweis.
- unbekannte oder gestoppte Ziele werden nicht autorisiert;
  verschwundene bestehende Einträge werden als Entzugskandidaten gemeldet.
- Einträge sind immer konkrete numerische CTIDs; VMs haben keinen Eingang in
  den LXC-Plan.
- Rendering erzeugt nur einen überprüfbaren Kandidaten. Schreiben, Besitz,
  Modus, atomarer Austausch und systemd-Aktivierung bleiben Installer-Gates.

## Zielarchitektur

1. **Discovery:** Proxmox-API liefert dynamische LXC-/VM-Inventarlisten.
   OS/Paketmanager werden zunächst als `unknown` geführt. Ein einmalig
   freigegebener, fester Gast-Probeweg darf diese Felder ausschließlich mit
   `cat /etc/os-release`, `dpkg-query --version`, `apt-get --version` und
   Pfad-Existenzprüfungen ergänzen. Keine freie Shell und kein `apt update`.
2. **Policy manager:** verbindet Inventar mit einer expliziten Policy
   (`discover_only` als Default oder der bewusst aktivierte Auto-Modus),
   plant atomare Allowlist-Diffs und entfernt stale/stopped/unsupported
   Autorisierungen ohne neue Berechtigungen durch bloße Erkennung.
3. **Installer:** `scripts/install-lxc-helper.sh` ist jetzt als sicherer,
   preflight-only-by-default Installer ergänzt. `--apply` ist explizit nötig;
   `--start` ist separat erforderlich. Er prüft Commit/Quellen, erkennt
   unsichere Ziele, installiert root-owned Helper/Unit/Allowlist und legt ein
   Rollback-Staging an. Eine vorhandene Allowlist wird erhalten; eine neue ist
   leer. Er erweitert keine Berechtigungen und startet den Agenten nicht. Bei
   bestehender `lxc_helper_enabled=false` bleibt die tatsächliche
   Agent-Anbindung bis zu einem separat geprüften Agent-Upgrade offen.
4. **HA-Onboarding:** Config-/Options-Flow soll Agent-Health, Helper-Status,
   Discovery-Mode und getrennte Statusgründe anzeigen. Änderungen dürfen
   keine Allowlist automatisch aktivieren; der Agent bleibt durchgehend
   install-disabled.
5. **Lifecycle:** add/remove/stop events werden beim nächsten bounded
   Inventory-Refresh erkannt. Nur der explizit gewählte Modus darf den
   Allowlist-Kandidaten aktualisieren; VMs bleiben Monitoring-only.

## Abnahme und offene Arbeit

Die isolierte Policy ist durch Tests für neue, gestoppte, unbekannte,
unsupported, stale und numerisch ungültige Ziele abzunehmen. Vor Stable fehlen
noch die sichere Gast-Probeweg, die persistente Policy-/Diff-Orchestrierung,
API-Felder für Helper-/Policy-Provenienz, die idempotente
Wiederherstellungsprüfung des Installers sowie der HA-Flow und die
End-to-End-Erstinstallation in einer isolierten Umgebung. Bis dahin ist
der produktive Helper- und Allowlist-Zustand unverändert und Stable bleibt
NO-GO.
