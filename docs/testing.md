# Phase 2.2 – Testdokumentation

Phase 2.2 erweitert die Suite um dynamische Fixture-Discovery, gestoppte bzw.
unbekannte Container, schmutzige Zigbee2MQTT-Repositories, Paperless-Recovery,
Capabilities, Authentifizierung, API-Pagination, große Antworten, Cursor und
persistierte Ereignisse. Der vollständige Lauf umfasst aktuell 21 Tests.

Die Kartenhelfer werden zusätzlich mit einem lokalen Node-Test-Harness geprüft:

```bash
node frontend/card-state.test.js
```

Browser-/HA-DOM-Tests und echte Lovelace-Renderings sind ohne HA-Testumgebung
BLOCKED/NOT RUN.

Ausführung aus dem Projektverzeichnis:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
python3 -m compileall -q agent tests
```

Abgedeckt sind gültige/ungültige Übergänge, explizite Verifikation vor Erfolg,
Idempotenz, parallele Starts, Timeouts, Restart-Recovery, Logbegrenzung und
Pagination, Secret-Filter, Versionsfehler, unbekannte/nicht unterstützte
Adapter, Ressourcen-Gates und deaktivierte Ausführung.

Die Tests verwenden ausschließlich `tempfile.TemporaryDirectory()` und
SQLite-Testdateien. Es werden keine produktiven Pfade, Ports, Dienste,
Home-Assistant-Instanzen oder Proxmox-Gäste angesprochen.

Nicht Bestandteil von Phase 2.1 sind HA-Fixtures, Hassfest, Frontend-Build,
Proxmox-API, Live-Agent, Integrationstests und reale Update-Postchecks.

## Phase 2.5 Status

- Python-Regression: **PASSED**, 24 Tests
- Node-Zustandshelfer: **PASSED**
- Chromium-Offline-Harness bei 390px: **PASSED**; Container, Jobphase und
  kein horizontaler Überlauf erkannt
- HA-2026.11-Laufzeit, Hassfest, HACS und Browser-Matrix mit mehreren Geräten:
  **BLOCKED/NOT RUN**

Der Playwright-Harness verwendet begrenzte Timeouts: Browserstart und
Navigation brechen nach 15 Sekunden ab, einzelne Aktionen nach 10 Sekunden
und die gesamte Matrix nach 150 Sekunden. Ein Suite-Timeout endet mit
Exit-Code 124 und einer eindeutigen Fehlermeldung. Browser und lokaler
Fixture-Server werden im `finally`-Pfad geschlossen; es gibt keine
automatischen Wiederholungen.
