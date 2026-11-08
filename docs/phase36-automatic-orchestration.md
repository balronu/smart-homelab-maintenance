# Phase 36 – automatische Einrichtung und sichere Orchestrierung

## Entwicklungsstatus

Diese Änderung verbindet die isolierten Verträge aus Phase 35, bleibt aber
außerhalb des Produktivsystems. Der offizielle Installer kann den festen
Discovery-Dienst und die vorhandenen Helper-Komponenten als atomare Staging-
Einheit bereitstellen; ohne `--apply` bleibt er ein Preflight. Ohne die
separate Startfreigabe wird kein Dienst gestartet und keine Allowlist geändert.

## Komponenten

* `discovery_socket.py`: fester Unix-Socket-Vertrag mit SO_PEERCRED,
  numerischer LXC-ID, Operation `probe`, Größenlimit, Timeout und serialisiertem
  Probe-Aufruf. VMs und freie Befehle werden abgewiesen.
* `scripts/smh-lxc-discovery.py` und die systemd-Unit: root-eigener,
  fest verdrahteter Transport für die vier OS/APT-Nachweise. Er ist nicht
  aktiviert und nicht auf `pve-home` installiert.
* `apply_controller.py`: Vorschau standardmäßig; atomare Allowlist-Anwendung
  nur mit explizitem `confirmed=True`, exklusiv serialisiert und ohne
  automatische Rechteerweiterung.
* `orchestration_status.py` und `/api/v1/orchestration`: nicht-sensitive
  Health-/Policy-/Reconcile-/Rollback-Felder für Agent und HA.
* HA-Optionsflow: Auswahl zwischen `discover_only` und `auto_eligible`, mit
  `discover_only` als sicherem Standard; echte Paketinstallation bleibt
  ausgeschlossen.

## Bewusst offene Punkte

1. Vollständige End-to-End-Erstinstallation in einer isolierten Root-/systemd-
   Testumgebung.
2. API-Verbindung des Reconcile-Controllers mit dem tatsächlichen Proxmox-
   Inventar und der aktiven Allowlist.
3. HA-Status-/Optionsmigration einschließlich Rückwärtskompatibilität.
4. Healthcheck, Audit-Log und Recovery-Abnahme über alle neun CI-Gates.
5. Separate Freigabe, bevor irgendein produktiver Helper, Socket oder Gastprobe
   aktiviert wird.

## English summary

Phase 36 adds a fixed peer-authenticated discovery socket contract, an
explicit serialized allowlist apply controller, non-secret orchestration
health fields, and a Home Assistant policy selector. `discover_only` remains
the default. The installer stays preflight-only unless explicitly applied,
and no production host, guest, VM, package manager, or allowlist was changed.
