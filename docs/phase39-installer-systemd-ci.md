# Phase 39 – automatisierte Installer-Abnahme

Der reale Root-/systemd-Nachweis läuft in einem separaten GitHub-Actions-Job
auf einem kurzlebigen `ubuntu-24.04`-Runner. Der Job ist kein Proxmox- oder
Home-Assistant-Produktivtest.

## Abnahmeschranke

Der Test prüft vor jeder Änderung, dass PID 1 systemd ist und die Zielpfade
noch keine Installation enthalten. Bei einer ungeeigneten Umgebung wird der
Test ohne Erfolgsmeldung beendet; ein Mock wird nicht als Installationspass
gewertet.

## Geprüfter Ablauf

1. Preflight ohne Änderungen.
2. Ephemeren systemd-Agent-Anker bereitstellen.
3. Helper-Installer mit `--apply` ausführen.
4. Root-Besitz, Modi, Unit-Validierung und leere Standard-Allowlist prüfen.
5. Separat mit `--start` starten und beide Unix-Sockets prüfen.
6. Wiederholungsinstallation auf unveränderte Allowlist prüfen.
7. Falschen erwarteten Commit ablehnen lassen (fail-closed vor Mutation).
8. Runner-Zustand über einen begrenzten Cleanup-Handler entfernen.

Der Job führt keine Proxmox-Gastbefehle, keine Paketaktionen, keine VM-
Zugriffe und keine Änderungen an `pve-home` aus. Die neun bestehenden
Repository-Gates bleiben unverändert; dieser Job liefert den zusätzlichen
realen Installer-Nachweis.

Der read-only Vorabvertrag `scripts/lxc-helper-preflight.py` liefert außerdem
JSON mit `decision` (`GO` oder `NO-GO`), einzelnen Checkstatuswerten,
`failed_checks`, `apply_authorization_required` und
`mutations_performed=false`. Ein `GO` ist nur eine Preflight-Aussage und
aktiviert keine Installation.

## Noch offene Abnahme

Der CI-Job ersetzt keine echte Proxmox-/HA-Liveintegration. Discovery,
Policy, Allowlist, API und HA werden weiterhin mit isolierten Inventar- und
Transportdaten geprüft. Ein produktives Helper- oder Allowlist-Apply bleibt
separat freigabepflichtig.
