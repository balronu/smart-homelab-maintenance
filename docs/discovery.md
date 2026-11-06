# Discovery

`DiscoveryService` arbeitet ausschließlich gegen ein injiziertes Backend.
`FixtureProxmoxBackend` repräsentiert die Phase-1-Containerliste; produktive
Proxmox-Befehle, Shell-Aufrufe und Netzwerkzugriffe existieren nicht.

## Adapterstatus

- **Zigbee2MQTT Zuhause:** lesende Git-/Versions-/Dienstfakten vorhanden;
  ein späterer Updateadapter ist nach Preflight-Prüfungen denkbar.
- **Zigbee2MQTT Wohnmobil:** bekannt schmutziger Git-Zustand, daher blockiert.
- **Paperless-ngx:** uv, Python, PostgreSQL, Redis, Dienste und Migrationsrisiken
  werden als Fakten modelliert; `manual_recovery_required` blockiert Updates.
- **APT:** Paketmanager und OS können erkannt werden, aber generische APT-
  Updates sind kein Anwendungsadapter und bleiben getrennt.
- **Docker/NPM und unbekannte Anwendungen:** ausschließlich lesend bzw. blockiert.

Neue Container erscheinen durch neue Backend-Datensätze ohne Codeänderung.
Nicht erkannte Anwendungen werden nicht automatisch als updatefähig bewertet.
