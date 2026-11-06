# Phase 2.2 – Offline-Architektur

Phase 2.2 ergänzt `discovery.py` und `api.py` auf derselben Domainbasis. Die
Discovery nimmt ein Backend-Protokoll entgegen; Fixtures sind die einzige
Quelle in dieser Phase. Die API bleibt transportneutral und wird durch den
In-Process-Handler getestet. Kein Modul startet Prozesse oder öffnet einen
produktiven Listener.

```text
api_models.py ──> security.py ──> jobs.py ──> SQLite (nur Test-/lokaler Pfad)
                       │              │
types.py <─────────────┘              └── errors.py
   │
versions.py       adapters.py ──> execution.py (in Phase 2.1 immer disabled)
discovery.py ────> api.py (versionierter, lesender Vertrag)

HA-Entities ──────> frontend/card-state.js ───> smart-homelab-maintenance-card.js
                         (kein direkter Agentzugriff, keine Tokens)
```

## Grenzen

- `types.py`: Container, Anwendungen, Jobanforderungen, Zustände, Phasen,
  Verifikations- und Ressourcenmodelle.
- `adapters.py`: explizite Registry. Unbekannte oder nicht unterstützte
  Anwendungen werden abgewiesen. Die Registry enthält keine Shell-Befehle.
- `versions.py`: konservativer numerischer Versionsparser; `latest` und andere
  unbestimmte Angaben werden nicht akzeptiert.
- `security.py`: Payload-Validierung, Shell-/Command-Injection-Filter,
  secret-freie Logwerte und Ressourcen-Gates.
- `api_models.py`: transportneutrale, geschlossene Job-Payloads.
- `jobs.py`: SQLite-Schema, Zustandsübergänge, eindeutige Idempotency-Keys,
  partielle Ziel-Sperre, begrenzte Logs und Recovery nach Prozessneustart.
- `execution.py`: bewusste Sperre; Phase 2.1 kann keinen Updateprozess starten.

Es gibt keinen Home-Assistant-Import, keinen Proxmox-Client, kein `subprocess`,
keinen Socket und keine produktive Datenbankverbindung.
