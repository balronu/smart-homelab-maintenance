# Phase 35 – automatische LXC-Discovery und Policy-Orchestrierung

## Status

Diese Phase liefert eine isolierte, nicht schreibende Orchestrierungsschicht.
Sie installiert keinen Helper, öffnet keinen produktiven Socket und führt
keine Gastprobe oder Simulation aus. `discover_only` bleibt der sichere
Standard.

## Ablauf

```text
Inventar → Policy laden → (nur auto_eligible) feste Discovery-Probe
→ Eignung → deterministischer Allowlist-Plan → Status/Provenienz
```

`reconcile()` arbeitet sequenziell, ohne Retries und ohne Allowlist-Schreibung.
Die Rückgabe enthält die Policy, jeden Probe-Zustand, den Beobachtungszeitpunkt
und einen exakten Plan mit numerischen IDs. Der Plan ist ein Kandidat für eine
später ausdrücklich autorisierte Anwendung.

## Policy-Schema

Die persistente JSON-Policy verwendet `schema_version: 1` und enthält:

* `mode`: `discover_only` oder ausdrücklich `auto_eligible`
* `generation`: monotone Konfigurationsgeneration
* `manual_authorized_ids`: konkrete numerische LXC-IDs

Fehlende, beschädigte, unsichere oder unbekannte Policies werden fail-closed
abgewiesen. Speicherung erfolgt atomar über eine temporäre Datei, `fsync()`
und `os.replace()` mit Modus `0600`. Das Modul verändert keine bestehende
Produktivkonfiguration.

## Discovery-Vertrag

Der Transport akzeptiert nur eine numerische LXC-ID und die feste Operation
`probe`. Die zulässigen Befehle sind fest im Vertrag hinterlegt:
`/etc/os-release`, `apt-get --version`, `dpkg-query --version` sowie die
Existenzprüfungen der beiden Binärdateien. Es gibt keine Shell, keine freien
Argumente, keinen VM-Pfad und keinen Simulationspfad. Antwortfelder und die
Ausgabegröße sind begrenzt und werden vor der Auswertung validiert.

Die eigentliche root-eigene Socket-/Peer-UID-Implementierung, Health-API,
HA-Onboarding und die autorisierte Anwendung des Allowlist-Plans bleiben
bewusst offen für die nächste Phase. Dadurch entsteht durch diese Änderung
keine neue produktive Berechtigung.

## Zustände und Fail-Closed-Regeln

`pass`, `unsupported`, `unknown`, `stopped`, `unauthorized` und
`probe_failed` bleiben getrennt. Nur laufende LXC-Records mit erfolgreichem
Debian-/Ubuntu- und APT-Nachweis werden im Modus `auto_eligible` als neue
Kandidaten geplant. VMs, ungültige IDs, gestoppte Gäste, fehlende Nachweise
und veraltete/fehlgeschlagene Probes erzeugen keine neue Berechtigung.

## Noch offene Phase-36-Arbeit

1. Root-eigenen Discovery-Socket mit SO_PEERCRED, Timeout und Ausgabelimit
   bereitstellen und unabhängig testen.
2. Policy-Migration/Recovery in den offiziellen Installer integrieren.
3. Einen einzelnen, serialisierten Apply-Controller mit Audit-Log und
   Rollback bauen.
4. Agent-API und HA-Konfigurationsdialog für Modus, Status und Fehler ergänzen.
5. Isolierte Erstinstallation und CI-Abnahme vor jeder Produktivfreigabe.
