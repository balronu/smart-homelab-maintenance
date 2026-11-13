# iOS-Scroll-Diagnose

Die Diagnose ist standardmäßig deaktiviert und verändert keine Scrollposition,
keine CSS-Eigenschaft und kein Touch-Ereignis. Sie wird ausschließlich
temporär über die Kartenkonfiguration aktiviert:

```yaml
type: custom:smart-homelab-maintenance-card
title: Smart Homelab Maintenance
scroll_diagnostics: true
```

In der Karte erscheinen dann **Diagnose starten**, **Diagnose beenden** und
**JSON kopieren**. Während der Messung einmal in der Karte wischen. Das JSON
enthält nur technische Daten:

- DOM-/Shadow-DOM- und Vorfahrenkette
- `scrollHeight`, `clientHeight`, `scrollTop`, Overflow-, Höhen-,
  `touch-action`- und Positionierungswerte
- erkannte Scrollcontainer
- Position von CT112, falls CT112 in der geladenen Liste vorhanden ist
- Touch-Ereigniszähler und Scrollbewegung während des Touches
- nicht-sensitive Laufzeitdaten zur Unterscheidung von Safari und nativer
  Home-Assistant-iOS-App (`userAgent`, Standalone-Modus, Viewport)

## Vergleich native App / Safari

Auf demselben iPhone zunächst Safari und danach die native Home-Assistant-App
öffnen. In beiden Oberflächen dieselbe Karte mit aktiviertem Diagnosemodus
laden, die Karte einmal von oben nach unten wischen und jeweils das JSON
kopieren. Verglichen werden insbesondere:

1. `runtime.userAgent`, `runtime.standalone` und
   `runtime.displayModeStandalone`;
2. `identifiedScrollContainer` und alle Vorfahren mit `overflowY`,
   `clientHeight` und `scrollHeight`;
3. `shadowDom.ct112.rect` sowie `ct112Position`;
4. `touch.touchmove` und `touch.scrollDeltaDuringTouch`.

Wenn `touchmove` ankommt, aber `scrollDeltaDuringTouch` null bleibt, während
ein Vorfahre `overflow: hidden`, eine feste Höhe oder einen kleineren
`clientHeight` als den benötigten Inhalt meldet, ist die Ursache ein
übergeordneter iOS-/HA-Layout- bzw. Scrollcontainer. Erst diese Messung darf
eine spätere Layoutkorrektur begründen.

Nach der Messung `scroll_diagnostics: true` wieder entfernen.
