# API v1

Die API ist in Phase 2.2 transportneutral und offline testbar. `ApiApplication.handle`
ist der In-Process-Testclient; ein späterer localhost-Adapter darf nur diesen
Vertrag verwenden. Der Healthcheck ist minimal und ohne Token erreichbar.

Alle übrigen Endpunkte verlangen `Authorization: Bearer <read-token>`.

| Methode | Pfad | Funktion |
|---|---|---|
| GET | `/api/v1/health` | Minimaler Offline-Healthcheck |
| GET | `/api/v1/capabilities` | Adapter-Capabilities, ohne Geheimnisse |
| GET | `/api/v1/containers?offset=&limit=` | paginierte Discovery |
| GET | `/api/v1/apps/{app_id}` | einzelne Anwendung |
| GET | `/api/v1/jobs?offset=&limit=` | begrenzte Jobübersicht |
| GET | `/api/v1/jobs/{job_id}` | Jobstatus ohne große Historie |
| GET | `/api/v1/jobs/{job_id}/events?after=&limit=` | Cursor-basierte Ereignisse |

Der lokale HTTP-Transport prüft Timeout, Antwortgröße, Bearer-Authentifizierung
und `schema_version`; abgebrochene oder ungültige Antworten werden als
strukturierte Transportfehler behandelt. Antworten besitzen `schema_version: "1"`, `request_id` und entweder `data`
oder ein strukturiertes `error`. Antwortgröße und Pagination sind begrenzt.
