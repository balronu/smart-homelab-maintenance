# Beta.14-Diagnose: Sections-Scrollen und Ressourcenwerte

## Ergebnis

Der echte iPhone-/HA-DOM konnte in dieser Untersuchung nicht gemessen werden:
der verwaltete Browser hatte keinen authentifizierten HA-Tab. Der iPhone-Fehler
ist deshalb nicht als endgültig behoben bestätigt.

Der reproduzierbare technische Verdachtsmoment ist jedoch eingegrenzt:
Home Assistant Sections verwendet bei `rows: "auto"` die natürliche Höhe. Der
`hui-section`-Pfad re-rendert seine Kartenliste nach dem Bubbling-Event
`card-updated`; die Karte meldete Änderungen durch das Öffnen von
`<details>` bisher nicht. Dadurch kann ein übergeordneter Wrapper eine alte
Höhe behalten und den unteren Karteninhalt abschneiden.

## Untersuchte Quellen

- HA 2026.11.0 / Frontend `20261028.4`: `hui-card.ts` delegiert
  `getGridOptions()` an die Custom Card; `hui-grid-section.ts` verwendet bei
  `rows: "auto"` normale Grid-Autozeilen; `compute-card-grid-size.ts` ignoriert
  `min_rows`, wenn `rows` nicht numerisch ist.
- `hui-section.ts` hört auf `card-updated` und aktualisiert seine Kartenliste.
- Die Karte nutzt Shadow DOM und native `<details>`-Elemente. Vor Beta.14 gab
  es keinen `ResizeObserver` und kein Größenänderungs-Event.

## Reproduktion

`frontend/sections-scroll-regression.html` bildet die relevante Sections-
Hierarchie nach: `section-container` → `section` → 12-Spalten-Grid →
Kartenwrapper. Der Negativpfad friert die Wrapperhöhe vor dem Öffnen von CT112
ein und setzt `overflow:hidden`; der letzte Eintrag wird abgeschnitten. Der
Beta.14-Pfad übernimmt die neue Höhe über `card-updated`.

Gemessene Fixturewerte (Chromium, 10 Container, CT112 geöffnet):

- iPhone 13: Legacy-Wrapper 1342 px, Karte 1539 px, abgeschnitten; Fix-
  Wrapper 1543 px, Karte 1539 px, CT112 erreichbar.
- iPad: Legacy 895 px / Karte 1092 px, abgeschnitten; Fix 1096 px / 1092 px,
  CT112 erreichbar.
- Desktop 1024/1440: Legacy 751 px / Karte 948 px, abgeschnitten; Fix 952 px /
  948 px, CT112 erreichbar.

Das ist ein realistischer Sections-Wrapper-Test und ein Beleg für den
Größenänderungsmechanismus, aber kein Beleg für das konkrete Safari/iOS-
Rendering. Ein echter iPhone-Praxistest bleibt erforderlich.

## RAM- und Speicherwerte

Der Live-State von `sensor.smart_homelab_maintenance_host` war verbunden, aber
`online: false` und enthielt nur Name, Release und Kernel; CPU/RAM/Speicher
waren dort nicht vorhanden. Zusätzlich hat
`ProxmoxInventoryBackend.host()`, `.containers()` und `.virtual_machines()` die
vom read-only Proxmox-Client gelieferten Ressourcenfelder verworfen. Beta.14
reicht diese vorhandenen Felder unverändert weiter. Fehlende Live-Werte werden
weiterhin als nicht verfügbar dargestellt, nie erfunden.

## Einstufung

- **Bestätigt:** `rows: "auto"` und `min_rows` sind nicht die Ursache; CT110–112
  sind in der Datenbasis vorhanden; Ressourcenfelder wurden im Backend-
  Projektionsschritt verloren.
- **Reproduziert:** Stale-Wrapperhöhe ohne Größenänderungs-Signal schneidet das
  Kartenende ab; das Signal behebt diesen Fixture-Fall.
- **Noch offen:** Ob genau dieser stale-height-Pfad die iOS-Home-Assistant-
  Instanz verursacht, weil der echte authentifizierte iPhone-DOM nicht
  verfügbar war.
