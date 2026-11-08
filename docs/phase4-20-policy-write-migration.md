# Beta.43 Policy-Write-Migration und Rollback

## Migration

1. Vor der Migration den offiziellen Preflight gegen den exakt geprüften
   Commit ausführen.
2. `install-lxc-helper.sh --apply` installiert die Helper-/Discovery-Dateien
   und die Unit, legt `/etc/smart-homelab-maintenance` als `root:root 0700` an
   und kopiert eine vorhandene Allowlist unverändert in das Staging.
3. Es werden keine neuen Container-Einträge erzeugt und keine Berechtigungen
   erweitert. Bestehende `root:root 0600`-Grants bleiben erhalten.
4. Erst nach separater Freigabe dürfen ausschließlich die erforderlichen
   Helper-/Discovery-Dienste gestartet werden. `execution_enabled=false` bleibt
   unverändert; kein Grant und kein Paketlauf ist Teil der Migration.
5. Danach über den Helper-Socket nur Read-back, Besitz/Modi, Unit-Sandbox und
   Health prüfen.

## Rollback

Der Installer legt vor dem Ersetzen der Dateien ein root-only Staging unter
`/var/lib/smart-homelab-maintenance/helper-rollback/<UTC-Zeitstempel>` an.
Bei einem fehlgeschlagenen Healthcheck wird nicht automatisch weitergemacht;
die vorige Helper-, Unit-, Discovery- und Allowlist-Datei bleibt dort für die
kontrollierte Wiederherstellung erhalten. Die Wiederherstellung erfordert eine
separate Freigabe und muss danach mit `systemd-analyze verify`, Besitzer-/Mode-
Read-back und einem Dienst-Healthcheck geprüft werden.

Die produktive Unit wird durch diesen Entwicklungsauftrag nicht verändert.
