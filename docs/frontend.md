# Lovelace-Karte

Die Quelle der Karte liegt unter `frontend/smart-homelab-maintenance-card.js`;
das ausgelieferte Paket liegt zusätzlich unter
`custom_components/smart_homelab_maintenance/frontend/`. Sie liest nur
Home-Assistant-Entitydaten (`hass`), niemals Agent-URLs oder Tokens.

## Eigenschaften

- responsive Grid-Layout nach tatsächlicher Kartenbreite (`auto-fit`), nicht
  nach Bildschirmbreite
- Light-/Dark-Mode über Home-Assistant-CSS-Variablen
- deutsche und englische Standardtexte anhand einer typgeprüften Auflösung von
  `hass.language`, `hass.locale` und `hass.config.language`; unbekannte oder
  fehlende Angaben fallen auf Englisch zurück
- automatische Erkennung von Host-, VM- und LXC-Entitäten
- echte CPU-, RAM-, Speicher- und Laufzeitwerte, sofern vorhanden
- Fortschrittsbalken nur bei vorhandenen Zählerständen
- Wartungsbereich ausschließlich mit laufenden Jobs und Read-only-Hinweis
- `getConfigElement()`, `getStubConfig()` und idempotente Registrierung in
  `window.customCards`
- VM- und LXC-Einträge sind als native, zugängliche `<details>`-Elemente
  aufklappbar; ihre DOM-Identität bleibt bei `hass`-Updates erhalten.
- Sections-Grid-Vertrag: `columns: "full"` und `rows: "auto"`; es wird keine
  feste Kartenhöhe oder verschachtelte Haupt-Scrollfläche erzeugt.

## Beta.14-Kandidat

Die Karte beobachtet ihre tatsächliche Hostgröße mit `ResizeObserver` und
meldet Änderungen als `card-updated` mit Bubbling über die Shadow-DOM-Grenze.
Das entspricht dem von Home Assistant verwendeten Sections-Aktualisierungspfad
für Karten. Die neue Fixture prüft einen absichtlich veralteten Wrapper-
Höhenwert und verlangt, dass der letzte Container sowie ein nachfolgendes
Dashboard-Element erreichbar bleiben. Das ist kein echter iPhone-Test.

## Beta-9-Kandidat

Die Datei wird ohne Buildschritt bytegleich in den Integrationspfad kopiert und
über `add_extra_js_url` mit Versionsquery registriert. Beta.9 bewahrt den
geöffneten Hostbereich bei erneuten `hass`-Updates, nutzt Container Queries für
die tatsächliche Kartenbreite und blendet unbekannte OS-Werte aus.

Lokale Prüfungen:

```text
node frontend/card-state.test.js
node --check frontend/card-state.js
node --check frontend/smart-homelab-maintenance-card.js
```

Beta.8 erkennt VMs und Container aus den tatsächlich gelieferten
`vmid`-/`container_id`-Attributen, unabhängig vom konkreten Entity-ID-Slug.
Der Laufzeitfehler bei einem objektförmigen `hass.locale` bleibt behoben. Das
Editor-DOM bleibt bei erneutem `setConfig()` stabil, sodass Fokus und
ungespeicherte Eingaben bei mobilen HA-Updates erhalten bleiben. Der
Playwright-Harness prüft zusätzlich iPhone-/iPad-Emulation, leere und unbekannte
Entity-Zustände, JavaScript-Fehler, fehlgeschlagene Requests, den Lovelace-
Editor-Lifecycle und Light-/Dark-Mode.

Der Playwright-Harness benötigt eine installierte `playwright`-Abhängigkeit.
Beta.14 prüft zusätzlich 0, 1, 10, 20 und 50 Container sowie das Erreichen
des Kartenendes in simulierten Sections-/Masonry-Layouts. Diese Fixtures sind
kein Beweis für ein echtes iOS-Home-Assistant-Rendering; der Praxistest bleibt
vor einer Veröffentlichung erforderlich.

Der Browser-Harness verwendet begrenzte Timeouts für Browserstart (15 s),
Navigation (15 s), Aktionen (10 s) und den gesamten Testlauf (150 s). Bei
Überschreitung wird Exit-Code 124 mit einer eindeutigen Fehlermeldung geliefert;
Browser und Fixture-Server werden anschließend geschlossen. Es gibt keine
unbegrenzten Wiederholungsversuche.
