# API v1

Die API ist transportneutral und offline testbar. `ApiApplication.handle` ist
der In-Process-Testclient; `agent.server` stellt denselben Vertrag später über
einen TLS-geschützten Listener bereit. Der Healthcheck ist minimal und ohne
Token erreichbar.

Alle übrigen Endpunkte verlangen `Authorization: Bearer <read-token>`. Die
administrative Recovery verlangt zusätzlich ein separates
`Authorization: Bearer <recovery-admin-token>`.

| Methode | Pfad | Funktion |
|---|---|---|
| GET | `/api/v1/health` | Minimaler Offline-Healthcheck |
| GET | `/api/v1/host` | Proxmox-Hoststatus |
| GET | `/api/v1/virtual-machines?offset=&limit=` | paginierte VM-Discovery |
| GET | `/api/v1/capabilities` | Adapter-Capabilities, ohne Geheimnisse |
| GET | `/api/v1/containers?offset=&limit=` | paginierte Discovery |
| GET | `/api/v1/apps/{app_id}` | einzelne Anwendung |
| GET | `/api/v1/jobs?offset=&limit=` | begrenzte Jobübersicht |
| GET | `/api/v1/jobs/{job_id}` | Jobstatus ohne große Historie |
| GET | `/api/v1/jobs/{job_id}/events?after=&limit=` | Cursor-basierte Ereignisse |
| POST | `/api/v1/jobs/{job_id}/reconcile` | Bestätigte, evidenzgebundene Recovery eines nicht gestarteten Jobs |
| GET | `/api/v1/updates` | Passive Updateprüfung aller autorisierten Ziele |
| GET | `/api/v1/policy` | Aktuelle Policy mit Generation |
| POST | `/api/v1/policy/prepare` | Bestätigungslose Policy-Vorschau |
| POST | `/api/v1/policy/apply` | Bestätigter Policy-Wechsel |
| POST | `/api/v1/orchestration/preview` | Explizite, nicht schreibende Eligibility-Preview |
| POST | `/api/v1/orchestration/apply` | Bestätigter, plan- und statusgeprüfter Allowlist-Apply |
| GET | `/api/v1/updates/{target}` | Ergebnis für `host`, `container:{vmid}` oder `vm:{vmid}` |
| POST | `/api/v1/updates/{target}/dry-run` | Bestätigte, feste Paketmanager-Simulation |
| POST | `/api/v1/updates/container:{vmid}/execute` | Bestätigtes, plan-gebundenes `apt update` plus `apt upgrade` |

Update results preserve the explicit status values `updates_available`,
`current`, `not_checked`, `unsupported`, `unauthorized`, `error`, `stale`, and
`unknown`; clients must not collapse these into a generic up-to-date result.
See [passive update detection](update-detection.md) for the target-authorization
boundary and the safe allowlist format.

Der lokale Transport prüft private HTTPS-URLs, Zertifikatskette, Timeout,
Antwortgröße und Bearer-Authentifizierung
und `schema_version`; abgebrochene oder ungültige Antworten werden als
strukturierte Transportfehler behandelt. Antworten besitzen `schema_version: "1"`, `request_id` und entweder `data`
oder ein strukturiertes `error`. Antwortgröße und Pagination sind begrenzt.
Der öffentliche Healthcheck enthält zusätzlich `agent_version`, damit eine
HA-Integration und der separat laufende Agent nicht unbemerkt aus
unterschiedlichen Beta-Ständen betrieben werden.
Die Update-POST-Routen akzeptieren nur feste, target-scoped Operationen.
`execute` benötigt `confirm=true`, einen frischen `plan_digest`, getrennte
Update-Berechtigung und `execution_enabled=true`; beliebige Shell-Kommandos,
VM-Ziele, Dist-Upgrades und Paketentfernungen sind ausgeschlossen.
Der Dry Run akzeptiert ausschließlich JSON `{\"confirm\":true}`. Es gibt keine
Route zur echten Updateausführung: `/execute` und `/update` werden auch bei
direktem API-Aufruf serverseitig abgewiesen. Der Server bindet standardmäßig nicht öffentlich, verlangt Zertifikat und
privaten Schlüssel, TLS ab 1.2 und ein systemd-Credential für das Bearer-Token.
Es gibt keine POST-Route für echte Updates oder beliebige Shell-Kommandos.

`/jobs/{job_id}/reconcile` akzeptiert ausschließlich `confirm=true`, die
passende numerische `container_id` und ein Evidence-Objekt. Für
`not_executed` müssen unter anderem Job-/APT-/Versions-/Marker-Prüfung positiv
bestätigt sowie Start, Paketmutation, Teil-Ausführung, aktive Paketprozesse,
Locks und Start-/Abschlussmarker negativ bestätigt werden. Die Transition ist
nur aus `manual_recovery_required` möglich, schreibt einen separaten
append-only Audit-Datensatz mit Evidence-Hash und setzt den Job auf
`reconciled_not_executed`. Sie markiert niemals einen Job als erfolgreich und
weist ausgeführte, teilweise ausgeführte, aktive oder unklare Zustände zurück.

Policy- und Orchestrierungsrouten verlangen ebenfalls einen Bearer-Token. Ein
Policy-Apply benötigt die aktuelle `generation` und `confirm=true`. Eine Preview
führt nur bei aktivem `auto_eligible` die festen, begrenzten Eligibility-Probes
für laufende Debian-/Ubuntu-LXCs aus; `discover_only` bleibt probe-frei. Die
Preview schreibt niemals Grants. Der Apply akzeptiert ausschließlich einen
unveränderten Preview-Token, führt die Probe gegen den aktuellen Bestand erneut
aus und delegiert den atomaren Allowlist-Schreibvorgang an den root-owned Helper.
Update-Grants werden durch diesen Pfad nie erzeugt.
## GET `/api/v1/execution-preflight`

Read-only report of the global update-execution gate and the required
preflight conditions. It never changes `execution_enabled`, grants, policy,
jobs, packages, or guest state. A `false` value remains fail-closed until a
separate administrative policy change is explicitly confirmed and read back.
