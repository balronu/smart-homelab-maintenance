# Job-Zustandsmodell

```text
queued -> preflight -> waiting_confirmation -> running -> postcheck -> succeeded
   │          │                 │                 │          │
   ├──────────┴─────────────────┴─────────────────┴──────────┴─> blocked/failed
   └───────────────────────────────────────────────────────────> cancelled
                                                   └───────────> timeout
                                                   └───────────> manual_recovery_required
```

Ein aktiver Zustand, der beim erneuten Öffnen des SQLite-Repositories gefunden
wird, wird zu `manual_recovery_required` überführt. Ein beendeter Prozess ist
kein Erfolgsnachweis. `succeeded` kann nur aus `postcheck` und nur mit
`Verification(preflight_passed=True, postcheck_passed=True)` entstehen.

Persistiert werden Job-ID, Ziel, Operation, erwartete Version, Idempotency-Key,
Bestätigungshash, Status, Phase, Fortschritt, Meldung, Fehlercode/-text,
Zeitpunkte und Verifikationsflags. Logs sind zeitlich geordnet, paginiert und
pro Job auf eine konfigurierbare Anzahl begrenzt.
