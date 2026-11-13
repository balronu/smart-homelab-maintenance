# Stable update execution / Stable-Updateausführung

## Deutsch

Der in Beta.34 eingeführte Updatepfad ist in Stable enthalten. Er bleibt ein
echter, aber ausdrücklich opt-in geschützter Updatepfad
für laufende Debian-/Ubuntu-LXCs mit APT. `simulation_authorized` erlaubt nur
den Dry Run; `update_authorized` erlaubt zusätzlich echte Updates. Beide
Berechtigungen, ein frischer Check, ein passender Plan-Digest und eine
explizite Bestätigung sind erforderlich.

Der Root-Helper akzeptiert nur numerische LXC-IDs und `read`, `simulate`,
`update`. `update` führt genau `/usr/bin/apt-get update` und danach
`/usr/bin/apt-get --yes --no-remove upgrade` seriell aus. Kein Dist-Upgrade,
keine Entfernung, keine freien Argumente, kein Host-/VM-Pfad und kein
automatischer Neustart. Timeout, Ausgabelimit und exklusiver Update-Lock gelten
für den gesamten Vorgang; die Antwort enthält beide Phasen mit Rückgabecodes.

`execution_enabled = false` bleibt der sichere Standard. Die HA-Karte aktiviert
den Button nur für einen frischen sicheren Plan mit `update_supported=true`.
Produktive Paketänderungen benötigen eine eigene Freigabe für den konkreten
LXC und genau einen begrenzten Lauf.

## English

The update path introduced in Beta.34 is included in Stable. It is a real but
explicitly opt-in update path for running Debian/Ubuntu
LXCs using APT. `simulation_authorized` permits only dry runs;
`update_authorized` additionally permits real updates. Both permissions, a
fresh check, a matching plan digest, and explicit confirmation are required.

The root helper accepts only numeric LXC IDs and fixed `read`, `simulate`, and
`update` operations. `update` runs exactly `apt-get update` followed by
`apt-get --yes --no-remove upgrade`, with no dist-upgrade, removal, free-form
arguments, host/VM path, or automatic reboot. Timeout, output limits, and an
exclusive update lock apply; both phases are returned with exit codes.

`execution_enabled = false` remains the safe default. The HA card enables the
button only for a fresh safe plan with `update_supported=true`. Productive
package changes require separate approval for the concrete LXC and one bounded
run.
