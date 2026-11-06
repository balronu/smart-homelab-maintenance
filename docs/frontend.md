# Lovelace-Karte

Die Karte liegt unter `frontend/smart-homelab-maintenance-card.js` und wird
über `card-state.js` mit DOM-freien Zustandshelfern versorgt. Sie liest nur
Home-Assistant-Entitydaten (`hass`), niemals Agent-URLs oder Tokens.

## Eigenschaften

- responsive Grid-Layout nach tatsächlicher Kartenbreite (`auto-fit`), nicht
  nach Bildschirmbreite
- Light-/Dark-Mode über Home-Assistant-CSS-Variablen
- deutsche und englische Standardtexte anhand von `hass.locale`
- dynamische Container und Anwendungen
- persistente offene Containerdetails und ausgewählte Job-ID
- Phasenanzeige, wenn keine echte Prozentzahl vorhanden ist
- Updatebuttons bleiben deaktiviert; unbekannte/blockierte Anwendungen zeigen
  keinen ausführbaren Updatezustand
- `getConfigElement()`, `getStubConfig()` und idempotente Registrierung in
  `window.customCards`

## Spätere HACS-Beta

Für eine Beta muss die gebaute Datei in den Paketpfad der Integration kopiert,
über eine versionierte HA-Frontend-Ressource geladen und bytegleich gegen das
Buildartefakt geprüft werden. Diese Phase führt keine HA-Installation und keine
öffentliche Veröffentlichung durch.
