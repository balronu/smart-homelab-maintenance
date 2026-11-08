# LXC update permissions / LXC-Updateberechtigungen

## Deutsch

Der Agent verwaltet Berechtigungen pro numerischem, laufendem LXC über den
geschützten Endpunkt `POST /api/v1/updates/container:<CTID>/permissions`.
Der Request muss `confirm: true` sowie die beiden booleschen Felder
`simulation_authorized` und `update_authorized` enthalten.

Simulation und echte Updates sind getrennt. Eine echte Updateberechtigung ist
nur zusammen mit der Simulationsberechtigung zulässig und bleibt zusätzlich
von `execution_enabled` sowie einem frischen, unveränderten Plan-Digest
abhängig. VMs, der Host, gestoppte LXCs, nicht nachgewiesene Systeme und
ungültige IDs werden abgewiesen. Änderungen werden atomar in einer
root-eigenen Datei mit Modus `0600` gespeichert; unsichere oder beschädigte
Dateien führen zu `fail-closed`.

Ein Dry-Run ist auch bei `current`/null verfügbaren Updates zulässig. Dabei
wird kein künstlicher Updateplan erzeugt und keine Paketliste aktualisiert.

## English

The agent manages permissions per numeric, running LXC through the protected
`POST /api/v1/updates/container:<CTID>/permissions` endpoint. Requests require
`confirm: true` and the two boolean fields `simulation_authorized` and
`update_authorized`.

Simulation and real updates are separate. Real-update authorization requires
simulation authorization and remains gated by `execution_enabled` and a fresh,
unchanged plan digest. VMs, the host, stopped LXCs, unproven systems, and
invalid IDs are rejected. Changes are atomic in a root-owned `0600` file;
unsafe or corrupt files fail closed.

A dry run is also allowed for `current`/zero available updates. It never
creates a synthetic plan or refreshes package indexes.
