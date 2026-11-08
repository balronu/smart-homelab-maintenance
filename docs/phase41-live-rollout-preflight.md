# Phase 41 – produktiver Beta.31-Rollout: Prüf- und Rückfallvertrag

Dieser Ablauf ist eine vorbereitete Freigabematrix, keine Installations- oder
Neustartfreigabe.

## Read-only Ausgangsprüfung

Vor jeder Änderung müssen auf dem Zielhost und über den bestehenden TLS/API-
Pfad dokumentiert werden:

- Agent-Version und API-Vertrag 1.1
- TLS-Health, Dienststatus, MainPID, `NRestarts`, InvocationID und monotone
  Startzeit
- genau ein Listener auf Port 48128 und unveränderter Port 8128
- Quellcommit, sauberer Checkout und erfolgreicher JSON-Preflight
- vorhandene Konfiguration, Zertifikatspfade, Besitzer/Rechte und Rollback-
  Stagings
- VM-/LXC-Inventar ohne Gastbefehle; gestoppte Gäste bleiben gestoppt

Der JSON-Preflight muss `decision=GO`, keine fehlenden Checks und
`mutations_performed=false` liefern. Das ist nur eine Voraussetzung; der
Apply-Schritt benötigt eine separate Freigabe.

## Einziger Upgradepfad

1. Exakten Beta.31-Checkout und Commit verifizieren.
2. Offiziellen Updater ohne Apply/Confirm ausführen.
3. Nur bei vollständigem PASS genau einen offiziellen
   `--apply --confirm`-Aufruf ausführen.
4. Den kontrollierten Agent-Neustart und die Readiness-Frist abwarten.
5. Beta.31/API 1.1, TLS, systemd, Lifecycle und Ports read-only nachprüfen.
6. Erst danach Helper-/Discovery-Preflight prüfen; `discover_only` bleibt der
   sichere Standard.

Keine selbst gebaute Stop-/Copy-/Start-Sequenz, keine Wiederholung und keine
produktive Gastprobe in diesem Ablauf.

## Abbruch und Rückfall

Bei jedem Quell-, TLS-, API-, Port-, Lifecycle-, Health- oder Berechtigungs-
fehler sofort stoppen. Nur der offizielle automatische Rollbackpfad darf auf
Beta.30 zurückführen. Danach Beta.30, API 1.1, TLS, Dienst, Ports,
`NRestarts`, InvocationID, Startzeit und Stagings erneut read-only prüfen.
Ein erfolgreicher Rollback ist `ROLLBACK`, nicht `SUCCESS`.

## Aktueller Stand

Der produktive Agent ist Beta.30; der Orchestrierungsendpunkt fehlt dort noch
und Helper/Discovery sind nicht aktiviert. PR #55 enthält den isoliert
geprüften Beta.31-Stand. Ein produktiver Upgrade-, Helper-, HA- oder
Gastnachweis wurde in Phase 41 nicht ausgeführt.
