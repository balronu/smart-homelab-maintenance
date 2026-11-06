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

## Beta-7-Kandidat

Die Datei wird ohne Buildschritt bytegleich in den Integrationspfad kopiert und
über `add_extra_js_url` mit Versionsquery registriert. Der Kandidat führt keine
HA-Installation und keine öffentliche Veröffentlichung durch.

Lokale Prüfungen:

```text
node frontend/card-state.test.js
node --check frontend/card-state.js
node --check frontend/smart-homelab-maintenance-card.js
```

Beta.7 behebt den Laufzeitfehler bei einem objektförmigen `hass.locale`. Das
Editor-DOM bleibt bei erneutem `setConfig()` stabil, sodass Fokus und
ungespeicherte Eingaben bei mobilen HA-Updates erhalten bleiben. Der
Playwright-Harness prüft zusätzlich iPhone-/iPad-Emulation, leere und unbekannte
Entity-Zustände, JavaScript-Fehler, fehlgeschlagene Requests, den Lovelace-
Editor-Lifecycle und Light-/Dark-Mode.

Der Playwright-Harness benötigt eine installierte `playwright`-Abhängigkeit;
ohne diese Abhängigkeit ist die Browsermatrix nicht ausgeführt.
