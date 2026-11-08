# Smart Homelab Maintenance

## Issue #63 · LXC update management (E2E completion status)

Der geprüfte Release-Kandidat ist eindeutig als `0.1.0-beta.43` versioniert.
Beta.42 bleibt der bestehende Produktivstand, bis eine separate
Installationsfreigabe erteilt wird.

The reviewed release candidate is uniquely versioned as `0.1.0-beta.43`.
Beta.42 remains the installed productive state until a separate installation
approval is granted.

## Beta.43 systemd policy-write fix / systemd-Policy-Write-Fix

Der root-eigene Helper schreibt die Policy weiterhin atomar in eine temporäre
Datei im selben Verzeichnis und ersetzt sie mit `os.replace()`. Die systemd-
Unit gibt dafür ausschließlich `/etc/smart-homelab-maintenance` frei, behält
`ProtectSystem=strict` und erteilt keine pauschale `/etc`-Schreibfreigabe.
Verzeichnis, Symlinks, Besitzer, Modi und Policy-Daten werden geprüft; Datei
und Verzeichnis werden synchronisiert. Der offizielle Installer legt das
Verzeichnis root-owned mit Modus `0700` an und erhält bestehende Grants.

The root-owned helper still writes atomically through a same-directory
temporary file and `os.replace()`. The systemd unit now grants write access
only to `/etc/smart-homelab-maintenance`, while retaining
`ProtectSystem=strict` and avoiding broad `/etc` write access. Directory,
symlink, ownership, mode and policy data are validated; both file and
directory are synchronized. The official installer creates the directory
root-owned with mode `0700` and preserves existing grants.

Die vollständige LXC-Update-E2E-Abnahme ist noch offen. CI prüft den festen
Helper-Vertrag und eine echte Paketinstallation in einem Wegwerf-Gastroot;
für die finale Abnahme ist weiterhin ein echter, nichtproduktiver Proxmox-
LXC-Testgast erforderlich. Produktive Paketaktionen bleiben deaktiviert.

The complete LXC update E2E acceptance is still open. CI checks the fixed
helper contract and a real package installation in a disposable guest root;
final acceptance still requires a real non-production Proxmox LXC test guest.
Productive package actions remain disabled.

## Beta.42 grant eligibility fix / Freigabe-Eignungsprüfung

Die erste Simulationsfreigabe nutzt nun eine strikt read-only Eignungsprüfung
über den authentifizierten Helper: laufender LXC, Debian/Ubuntu aus
`/etc/os-release` und vorhandene APT-Binaries. Widerruf benötigt keine erneute
Eignungsprüfung; unbekannte oder widersprüchliche Ziele bleiben gesperrt.

The first simulation grant now uses a strict read-only helper probe: running
LXC, Debian/Ubuntu from `/etc/os-release`, and present APT binaries. Revocation
does not require a fresh eligibility probe; unknown or contradictory targets
remain denied. No package command is run by the probe.

## Beta.41 policy migration fix / Policy-Migrationsfix

Die bestehende root-owned Policy bleibt absichtlich `root:root 0600`. Der
unprivilegierte Agent greift deshalb nicht direkt auf die Datei zu, sondern
verwendet ausschließlich den per `SO_PEERCRED` geschützten root-eigenen
Helper-Socket für `policy_read` und `policy_set`. Der Helper schreibt atomar
und fail-closed; `execution_enabled = false` sowie getrennte Simulations- und
Updateberechtigungen bleiben unverändert. Dieser Fix ist vorbereitet, aber
nicht produktiv installiert.

The existing root-owned policy intentionally remains `root:root 0600`. The
unprivileged agent therefore never reads it directly and uses only the
`SO_PEERCRED`-protected root helper socket for `policy_read` and `policy_set`.
The helper writes atomically and fails closed; `execution_enabled = false` and
separate simulation/update permissions remain unchanged. This fix is prepared
but not installed productively.

Der Entwicklungsstand erweitert den opt-in Updatepfad für ausdrücklich
autorisierte laufende Debian-/Ubuntu-LXCs. Simulation und echte Updates haben
getrennte Berechtigungen und können pro LXC über den geschützten Agent-Endpunkt
verwaltet werden. Ein frischer Plan-Digest und eine Bestätigung sind Pflicht.
Ein Dry-Run ist auch bei null verfügbaren Updates möglich. Der sichere Standard
`execution_enabled = false` bleibt unverändert.
Es gibt kein Dist-Upgrade, keine Paketentfernung, keine VM-/Host-Aktion und
keinen automatischen Neustart. Siehe
[`docs/update-execution-beta34.md`](docs/update-execution-beta34.md). Die
Berechtigungsverwaltung ist in
[`docs/update-permissions.md`](docs/update-permissions.md) beschrieben.

The development branch provides an opt-in update path for explicitly authorized
running Debian/Ubuntu LXCs. Simulation and real updates use separate
permissions and can be managed per LXC through the protected agent endpoint. A
fresh plan digest and explicit confirmation are required. A dry run is also
available when zero updates are present. The safe default
`execution_enabled = false` remains unchanged. There is no dist-upgrade,
package removal, VM/host action, or automatic reboot. See
[`docs/update-execution-beta34.md`](docs/update-execution-beta34.md) and
[`docs/update-permissions.md`](docs/update-permissions.md).

## Beta.32: sichere Orchestrierungsanzeige und Helper-Bereitschaft

Beta.32 ergänzt den read-only Orchestrierungsstatus für Helper, Discovery-Socket,
Integrität und `discover_only`. Home Assistant zeigt fehlende Helper sicher als
nicht verfügbar an; die Integration aktiviert weder Helper, Socket, Allowlist
noch Gastzugriffe automatisch. Der externe Agent bleibt ein separat versionierter
Dienst. Die Beta.31-UI- und VM-Grenzen bleiben unverändert.

## Beta.32: safe orchestration status and helper readiness

Beta.32 adds the read-only orchestration status for helper, discovery socket,
integrity, and `discover_only`. Home Assistant reports a missing helper as
unavailable; the integration never activates a helper, socket, allowlist, or
guest access automatically. The external agent remains separately versioned.
The Beta.31 UI and VM boundaries remain unchanged.

Beta.31 hält die beiden Aktionsschaltflächen in einer festen,
touch-tauglichen Zeile; Ergebnis, Paketanzahl, Sicherheitsstatus und
aufklappbare Paketdetails stehen darunter. Lange Paketnamen und Versionen
brechen ohne horizontalen Überlauf um. **Updates installieren** bleibt
dauerhaft deaktiviert.

Die Host-Simulation bleibt unverändert read-only. LXC-Simulationen verwenden
später nur den festen, optionalen Helper-Pfad nach expliziter Ziel-Allowlist;
im Kandidaten ist kein produktiver Helper aktiviert. VMs bleiben dauerhaft
Monitoring-only: Es gibt keine VM-Paketprüfung, keine VM-Simulation und keinen
Aufruf von `pct exec` oder einem anderen VM-Update-Runner. VM-Karten zeigen
weiterhin Name, Laufstatus und Ressourcen sowie den Hinweis zur Updatefunktion
des Gastbetriebssystems. Die vollständige Matrix steht in
[`docs/beta31-simulation-readiness.md`](docs/beta31-simulation-readiness.md).

Phase 28 präzisiert den LXC-Gate: Ein laufender, ansonsten geeigneter
Container bleibt gesperrt, bis OS/APT passiv geprüft, der feste Root-Helper
separat freigegeben installiert und genau diese CTID in einer root-eigenen
Allowlist eingetragen wurde. Fehlt der Helper bei einem geprüften Ziel, meldet
die API `helper-unavailable`; die Karte aktiviert keine Aktion automatisch.
Eine nicht autorisierende Vorlage liegt unter
[`deploy/lxc-apt-allowlist.example.toml`](deploy/lxc-apt-allowlist.example.toml).

Phase 28 clarifies the LXC gate: a running, otherwise suitable container
remains blocked until its OS/APT facts are reviewed, the fixed root helper is
separately approved and installed, and exactly that CTID is placed in a
root-owned allowlist. A missing helper reports `helper-unavailable`; no action
is enabled automatically.

Beta.31 keeps the two action buttons in a stable touch-friendly
row and renders simulation results below it. Host simulation remains
read-only. LXC simulation is opt-in per explicitly authorized target and is
not enabled in production. VMs are permanently monitoring-only: no VM package
check, simulation, `pct exec`, or other VM update runner is used. Real package
installation is implemented as an opt-in path, but remains disabled by
default and has not yet passed the required real non-production Proxmox-LXC
E2E acceptance.

## Phase 35: automatische LXC-Discovery (Draft, kein Release)

Die Entwicklungsarchitektur kennt keine fest eingetragenen CTIDs. Eine
versionierte Policy verwendet standardmäßig `discover_only`; nur eine
ausdrücklich gewählte `auto_eligible`-Policy darf nach einer festen,
lesenden Probe laufende Debian-/Ubuntu-LXCs mit APT als Kandidaten planen.
Gestoppte Gäste, VMs, fehlende oder veraltete Nachweise und unbekannte Systeme
bleiben gesperrt. Die Orchestrierung erzeugt zunächst nur einen atomar
prüfbaren Allowlist-Plan; Helper-Installation, Socket, HA-Onboarding und die
produktive Anwendung sind noch nicht Bestandteil dieses Draft-Stands.

## Phase 35: automatic LXC discovery (draft, not a release)

The development architecture does not contain hard-coded CTIDs. A versioned
policy defaults to `discover_only`; only an explicitly selected
`auto_eligible` policy may plan running Debian/Ubuntu LXCs with APT after a
fixed read-only probe. Stopped guests, VMs, missing or stale evidence, and
unknown systems remain blocked. The orchestration first produces an atomic,
reviewable allowlist plan; helper installation, socket deployment, HA
onboarding, and production application are not included in this draft.

Phase 36 adds a separately testable discovery-socket contract, serialized
allowlist apply controller, machine-readable orchestration status, and the
`discover_only`/`auto_eligible` HA options-flow. The official installer stays
preflight-only by default; this does not authorize production activation or
real package installation.

Phase 37 adds an isolated end-to-end harness for the complete inventory,
probe, policy, plan, explicit apply, audit, recovery and status flow. It uses
temporary files and mocked transports only; it is not a productive installer
run and does not authorize helper or allowlist activation.

Phase 39 adds a separate GitHub Actions acceptance job on an ephemeral
root/systemd runner. It exercises the real helper installer, repeat
installation, permissions, socket health and fail-closed source validation.
It does not touch Proxmox or Home Assistant production and does not replace
the separately required Proxmox/HA live acceptance.

Phase 41 documents the read-only Beta.31 rollout gate, the machine-readable
helper preflight, the single official upgrade path and the fail-closed
rollback contract. It does not authorize a production upgrade.

Phase 45 exposes the non-secret helper/discovery installation status through
`/api/v1/orchestration` and the Home Assistant helper-status entity. A missing
helper is reported as unavailable, not as authorization; `discover_only`
remains the safe default and no helper, socket or allowlist is activated by
the integration.

Phase 45 exposes the non-secret helper/discovery installation status through
`/api/v1/orchestration` and the Home Assistant helper-status entity. A missing
helper is reported as unavailable rather than authorized; `discover_only`
remains the safe default and the integration never activates a helper, socket,
or allowlist by itself.

## Beta.30: Mobile UI und dauerhafter VM-Ausschluss

Dieser Entwicklungsstand verbessert die mobile Darstellung von Simulationen
und liefert eine explizite Eignungsanzeige für Host, LXC und VM. LXC-Ziele
bleiben bis zu einer ausdrücklichen, geprüften Allowlist-Freigabe gesperrt;
VMs werden niemals über `pct exec` angesprochen, solange kein unterstützter
Gasttransport vorhanden ist. Der Installationsbutton bleibt dauerhaft
deaktiviert.

This Beta.30 candidate improves mobile simulation rendering and makes the
permanent VM exclusion explicit. LXC targets remain blocked until an explicitly
reviewed allowlist is enabled; VMs are never sent through `pct exec` or another
update runner. The install button remains permanently disabled.

Die zweisprachigen Release Notes liegen unter
[`docs/releases/v0.1.0-beta.30.md`](docs/releases/v0.1.0-beta.30.md).

## Beta.29: Sichere systemd-Lebenszyklusprüfung

Beta.29 erweitert die Beta.28-Restart-Erkennung um `InvocationID` und den
monotonen Prozessstartzeitpunkt. Der erwartete kontrollierte Wechsel von der
alten zur neuen systemd-Instanz bleibt zulässig; fehlende oder ungültige
`NRestarts`-Werte, Anstiege, unerwartete Rückgänge/Resets sowie spätere
Lebenszykluswechsel führen sicher zum Rollback. Der Beta.28-APT-Parser für
`amd64`/`all` bleibt enthalten und der Installationsbutton deaktiviert.

Beta.29 extends the Beta.28 restart detection with `InvocationID` and the
monotonic main-process start timestamp. The expected controlled transition
from the old to the new systemd instance remains allowed; missing or invalid
`NRestarts` values, increases, unexpected decreases/resets, and later
lifecycle changes fail closed into rollback. The Beta.28 APT parser for
`amd64`/`all` remains included and the install button stays disabled.

Die zweisprachigen Release Notes liegen unter
[`docs/releases/v0.1.0-beta.29.md`](docs/releases/v0.1.0-beta.29.md).

## Beta.28: APT-Architekturspalte und stale-Status-Lebenszyklus

Beta.28 korrigiert das Parsen von `apt list --upgradable` für die reguläre
Architekturspalte (`amd64`, `all`). Dadurch bleiben installierte Versionen im
kanonischen Plan-Digest erhalten: identische Pläne werden unabhängig von ihrer
Reihenfolge akzeptiert, echte Paket- oder Versionsabweichungen weiterhin sicher
blockiert. Der Installationsbutton bleibt dauerhaft deaktiviert.

Beta.28 fixes parsing of the regular architecture column (`amd64`, `all`) in
`apt list --upgradable`. Installed versions therefore remain in the canonical
plan digest: identical plans are accepted independent of order, while real
package or version changes remain safely blocked. The install button stays
permanently disabled.

Der Updater bindet die Restart-Prüfung zusätzlich an `InvocationID` und den
monotonen Startzeitpunkt der neuen systemd-Instanz. Fehlende, ungültige,
gestiegene oder nach dem neuen Start veränderte `NRestarts`-Werte sowie ein
unerwarteter Lebenszykluswechsel führen sicher zum Rollback; der erwartete
Wechsel von der alten zur neuen Unit-Instanz bleibt zulässig.

The updater also binds restart validation to the new systemd `InvocationID` and
monotonic main-start timestamp. Missing, invalid, increased, or changed
`NRestarts` values after the new start, as well as an unexpected lifecycle
change, fail closed into rollback; the expected old-to-new unit transition
remains allowed.

Der HA-Coordinator hält das letzte Dry-Run-Ergebnis getrennt von den aktuellen
Update-Metadaten im Arbeitsspeicher. Ein alter stale-Status kann deshalb bis zu
einer neuen Dry-Run-Antwort neben einem frischen Updatecheck sichtbar bleiben;
Beta.28 löscht oder manipuliert diesen Zustand nicht automatisch.

The HA coordinator keeps the last dry-run result separately from current update
metadata in memory. An old stale result can therefore remain visible alongside
a fresh update check until a new dry-run response; Beta.28 does not delete or
mutate that state automatically.

Die zweisprachigen Release Notes liegen unter
[`docs/releases/v0.1.0-beta.28.md`](docs/releases/v0.1.0-beta.28.md).

## Beta.27: Restart-Race-Erkennung und sichere Rollbacks

Beta.27 erkennt systemd-Restarts während des Agent-Upgrades auch dann, wenn
ein späterer Versuch noch erfolgreich antwortet. Der Updater prüft den
Restart-Zähler vor dem Austausch und unmittelbar nach dem Healthcheck; jeder
Anstieg führt zum bestehenden sicheren Rollback. Damit kann ein Upgrade nach
wiederholten `Address already in use`-Fehlern nicht mehr fälschlich mit Exit 0
enden. Die Beta.22→Beta.26-`TIME-WAIT`-/`SO_REUSEADDR`-Ursache ist isoliert
reproduziert und dokumentiert.

Beta.27 detects systemd restarts during an agent upgrade even when a later
attempt responds successfully. The updater records the restart counter before
the swap and immediately after the healthcheck; any increase triggers the
existing safe rollback. An upgrade can therefore no longer report exit 0 after
repeated `Address already in use` failures. The Beta.22→Beta.26
`TIME-WAIT`/`SO_REUSEADDR` cause is reproduced and documented.

Die zweisprachigen Release Notes liegen unter
[`docs/releases/v0.1.0-beta.27.md`](docs/releases/v0.1.0-beta.27.md).

## Beta.26: Port-Gate-Forensik und sichere Upgrade-Rennen

Beta.26 erweitert die Beta.25-Lifecycle-Korrektur um eine forensische
Portprüfung: aktive TCP-Zustände und eine aktive systemd-Unit blockieren den
Start, während ausschließlich der terminale, kernelverwaltete `TIME-WAIT`
Zustand ausgenommen wird. Eine zweite Prüfung unmittelbar vor dem Start
schließt das Stop-/Swap-/Start-Rennen. PID-, Cgroup- und Socket-Diagnose bleibt
nicht-sensitiv; Rollback-Stagings werden nicht gelöscht.

Beta.26 extends the Beta.25 lifecycle fix with forensic port gating: active
TCP states and an active systemd unit block startup, while only terminal,
kernel-owned `TIME-WAIT` is exempted. A second check immediately before start
closes the stop/swap/start race. PID, cgroup, and socket diagnostics remain
non-sensitive; rollback staging is never deleted.

Die zweisprachigen Release Notes liegen unter
[`docs/releases/v0.1.0-beta.26.md`](docs/releases/v0.1.0-beta.26.md).

## Beta.25: Agent-Lifecycle und Port-Bind-Race

Der externe Agent beendet seinen HTTPS-Server bei Stop-Signalen kontrolliert
und schließt Port 48128, bevor systemd einen neuen Prozess starten kann. Der
Updater prüft die Portfreigabe nach dem Dienststopp und bricht bei einem noch
belegten Port sicher ab; ein längeres Readiness-Timeout ersetzt diese Prüfung
nicht. Historische und fehlgeschlagene Rollback-Stagings werden nicht gelöscht.

The external agent now performs controlled signal shutdown and closes port
48128 before systemd can start another process. The updater verifies the port
after stopping the service and safely aborts while it is still occupied; a
longer readiness timeout is not used as a substitute. Historical and failed
rollback staging directories are never deleted automatically.

Read-only Home-Assistant-Integration, Lovelace-Karte und offline testbarer
Wartungsagent für private Homelab-Umgebungen.

Die zweisprachigen Release Notes liegen unter
[`docs/releases/v0.1.0-beta.25.md`](docs/releases/v0.1.0-beta.25.md).

## Beta.24: Dry-Run-Planvergleich und Kartenanzeige

Beta.24 normalisiert Updatepläne vor dem Vergleich. Dadurch wird ein identischer
Plan aus passiver APT-Prüfung und `apt-get --simulate` nicht mehr nur wegen
unterschiedlicher Paket-Reihenfolge als veraltet abgebrochen. Echte Plan-
abweichungen bleiben sicher blockiert. Unbekannte RAM-Werte werden nicht als
0 % angezeigt; Gastzugriffsfehler werden auf Deutsch dargestellt und die beiden
Aktionsschaltflächen bleiben responsiv stabil.

Die zweisprachigen Release Notes liegen unter
[`docs/releases/v0.1.0-beta.24.md`](docs/releases/v0.1.0-beta.24.md).

## Beta.23: Dry-Run-Servicefehler behoben (Kandidat)

Der `smart_homelab_maintenance.dry_run`-Service wählt seinen Coordinator nun
robust aus, auch wenn der Lovelace-Aufruf keine `entry_id` mitsendet. Interne
Setup-Metadaten wie `card_registered` werden nicht mehr als Transportobjekt
verwendet. Damit verschwindet der Fehler `bool has no attribute transport`.

Der Service fordert weiterhin eine explizite Read-only-Bestätigung und die
Home-Assistant-Serviceantwort an. Erfolgsantworten, HTTP-/TLS-Fehler,
Zeitüberschreitungen und ungültige Ziele werden strukturiert behandelt. Echte
Paketupdates bleiben serverseitig deaktiviert; der Button **Updates
installieren** bleibt ohne ausführbaren Pfad. **Update simulieren** bleibt bei
Host, VMs und LXCs sichtbar; bei nicht autorisierten, nicht unterstützten,
ungeprüften oder veralteten Zielen ist die Aktion ausgegraut und begründet.
Die beiden Aktionen sind responsiv angeordnet und verändern keine bestehenden
Aufklapp- oder Scrollzustände. Details stehen in
[`docs/releases/v0.1.0-beta.23.md`](docs/releases/v0.1.0-beta.23.md).

## Beta.20: vollständige Updateverwaltung ohne Ausführung

Dieser Entwicklungsstand trennt die passive APT-Cache-Auswertung vom bewusst
angeforderten Dry Run. Nur ausdrücklich allowlistete, laufende Debian-/Ubuntu-
Ziele können später geprüft werden; VMs ohne autorisierten Gastzugriff und
gestoppte LXCs werden nicht angesprochen. Der Button **Updates installieren**
ist sichtbar, dauerhaft deaktiviert und besitzt keinen Serviceaufruf. Echte
Updateausführung bleibt auch bei manipulierten Frontend-Anfragen serverseitig
gesperrt.

Die zweisprachigen Release Notes liegen unter
[`docs/releases/v0.1.0-beta.20.md`](docs/releases/v0.1.0-beta.20.md). Beta.20
ist als Prerelease veröffentlicht; der Agent wird weiterhin separat aktualisiert.

## Beta.21: sicherer LXC-Gastzugriff

Der Beta.21-Kandidat ergänzt einen optionalen, root-seitigen Unix-Socket-Helper
für ausdrücklich allowlistete LXC-Ziele. Der Helper akzeptiert ausschließlich
die festen Operationen `read` und `simulate`, prüft die CT-Allowlist bei jeder
Anfrage und lehnt alle anderen Befehle, Pfade und Ziele ab. Der Agent bleibt
standardmäßig deaktiviert (`lxc_helper_enabled = false`); eine bloße HACS-
oder Agent-Aktualisierung aktiviert den Gastzugriff nicht. Beta.21 ist als
GitHub-Prerelease veröffentlicht. Details und die
separaten Freigabegates stehen in
[`docs/lxc-apt-helper.md`](docs/lxc-apt-helper.md) und
[`docs/security.md`](docs/security.md).

## Beta.22: sicherer Agent-Preflight

Beta.22 übernimmt den gehärteten Agent-Updater. Eindeutig historische
Rollback-Staging-Stände bleiben erhalten und blockieren den Preflight nicht,
während aktive, beschädigte oder mehrdeutige Zustände weiterhin sicher stoppen.
Der API-Vertrag bleibt 1.1; Root-Helper, Socket und LXC-Allowlist bleiben
standardmäßig deaktiviert. Beta.22 ist als GitHub-Prerelease veröffentlicht.
Details stehen in
[`docs/releases/v0.1.0-beta.22.md`](docs/releases/v0.1.0-beta.22.md).

## Beta.19: Dry Runs und passive Update-Erkennung

Beta.19 behebt den Lovelace-Aufruf für `smart_homelab_maintenance.dry_run`:
Die Karte fordert die verpflichtende Home-Assistant-Serviceantwort an und
zeigt Paketänderungen, Warnungen, Sicherheitsbewertung, Fehler und
Zeitüberschreitungen sichtbar an. Die passive Update-Erkennung bewahrt
außerdem die eindeutigen Zustände aktuell, Updates verfügbar, noch nicht
geprüft, nicht unterstützt, nicht autorisiert, fehlgeschlagen, veraltet und
unbekannt. Echte Updates bleiben deaktiviert.

Der separate Agent-Updater ist gegen einen
Restart-/Readiness-Race gehärtet: Der TLS-Healthcheck wird innerhalb eines
begrenzten Zeitfensters wiederholt, ein Fehler führt über einen EXIT-sicheren
Rollbackpfad zurück zum vorherigen Agent-Code, und Rollback-Staging wird nicht
automatisch gelöscht. Diese Korrektur ist in Beta.20 enthalten; der produktive
Agent muss separat auf eine kompatible Agent-Version aktualisiert werden.

## Beta.18: gemeinsamer Versions- und Updatevertrag

Integration, Karte und Agent tragen dieselbe Beta-Version. Der Agent meldet
zusätzlich den API-Vertrag über `/api/v1/health`. Home Assistant bewertet die
Kombination als `current`, `outdated`, `incompatible` oder `unknown` und zeigt
die Abweichung sichtbar an. Ein HACS-Update aktualisiert niemals automatisch
den separat laufenden Agenten.

Der vorbereitete Agent-Prozess in `scripts/upgrade-agent.sh` prüft Commit,
Quellintegrität, TLS-CA, Dienst und Healthcheck. Der mutierende Pfad benötigt
explizit `--apply --confirm`, hält während des Healthchecks einen temporären
Rollback-Stand vor und stellt ihn bei einem fehlgeschlagenen Healthcheck
wieder her. Er verändert weder Proxmox, VMs noch LXCs.

## Status

Beta.22-Prerelease: Der Agent-Updater klassifiziert historisches Rollback-
Staging sicher und bewahrt es unverändert. Der optionale root-seitige
LXC-Helper prüft Peer-UID,
Allowlist, feste Operationen, Laufstatus, Timeout und Ausgabelimit pro Anfrage.
Der Helper ist nicht installiert oder aktiviert; echte Paketupdates bleiben
serverseitig gesperrt. Die zweisprachigen Release Notes stehen in
[`docs/releases/v0.1.0-beta.22.md`](docs/releases/v0.1.0-beta.22.md).

Beta.19-Prerelease: Dry-Run-Serviceantworten und passive Update-Erkennung
sind veröffentlicht. Der Dry-Run-Button verarbeitet den verpflichtenden
Service-Response-Vertrag; die Update-Zustände werden nicht als „aktuell“
fehlklassifiziert. Die vollständige Beschreibung steht in
[docs/releases/v0.1.0-beta.19.md](docs/releases/v0.1.0-beta.19.md).

Beta.18-Prerelease: gemeinsamer Versions-/API-Vertrag für Integration, Karte
und Agent sowie ein ausdrücklich bestätigungspflichtiger Agent-Updatepfad.
Die responsive Lovelace-Karte behält stabile dynamische Höhe, aufklappbare
Host-/VM-/LXC-Details und ein Größenänderungssignal für das Home-Assistant-
Sections-Layout. Eine echte iOS-Home-Assistant-Praxisprüfung steht noch aus;
der Scrollfehler ist nicht als behoben bestätigt.
Letzter veröffentlichter Release: [v0.1.0-beta.18](https://github.com/balronu/smart-homelab-maintenance/releases/tag/v0.1.0-beta.18).

Die passive Update-Erkennung unterscheidet explizit aktuell, Updates
verfügbar, noch nicht geprüft, nicht unterstützt, nicht autorisiert,
fehlgeschlagen, veraltet und unbekannt. Die ausführliche deutsch/englische
Beschreibung steht in [docs/update-detection.md](docs/update-detection.md).

Passive update detection explicitly distinguishes current, updates available,
not checked, unsupported, unauthorized, failed, stale, and unknown states. See
[docs/update-detection.md](docs/update-detection.md).
Der abschließende Praxistest in der Home-Assistant-iOS-App steht noch aus.
Updateausführung ist deaktiviert. Agent-,
Proxmox- und Containerzugriffe müssen vor einer späteren Aktivierung separat
konfiguriert und geprüft werden.

Beta.17 enthält passive Paketprüfungen für nachweislich unterstützte
Debian-/Ubuntu-Ziele und einen ausdrücklich bestätigten `apt-get --simulate`
Dry Run. Paketlisten werden nicht aktualisiert, Pakete werden nicht installiert
und Systeme werden nicht neu gestartet. Eine spätere Ausführung bleibt
serverseitig gesperrt und benötigt eine eigene, separat freizugebende Phase;
ein deaktivierter UI-Button allein wäre keine Sicherheitsgrenze.

Beta.16 isoliert Fehler der optionalen Update-Abfrage vom Kerninventar. Wenn
der Update-Endpunkt ausfällt, bleiben Host, VMs und LXCs sichtbar und der
Updatezustand wird als unbekannt gemeldet. Intervall-Refreshes werden über den
thread-sicheren Home-Assistant-Scheduler eingeplant.

Beta.17 ergänzt einen versionierten Agent-Healthcheck und eine robuste
Ressourcenprojektion. Fehlende Proxmox-Werte werden nicht als null erfunden;
VM-Gast-Freiräume werden nur angezeigt, wenn eine Datenquelle sie tatsächlich
liefert. Host, VM und LXC-Ressourcen sind in der Karte eindeutig beschriftet.
Für korrekte Beta.17-Ressourcen müssen Home-Assistant-Integration und der
separat laufende Wartungsagent gemeinsam auf Beta.17 aktualisiert werden;
nur die HACS-Integration zu aktualisieren ersetzt den Agenten nicht.

## Bestandteile

```text
custom_components/smart_homelab_maintenance/  Home-Assistant-Integration
frontend/                                     Lovelace-Karte
agent/                                        Offline-Agent-Kern
tests/                                        Offline- und Laufzeittests
docs/                                         öffentliche technische Doku
```

## Installation

Die Karte ist im Integrationspaket enthalten. Beim Laden der Integration wird
sie als versionierte Frontend-Ressource registriert und im Lovelace-
Karteneditor angeboten; eine manuelle YAML-Ressource ist dafür nicht nötig.

1. Für die Integration das Repository als Marketplace-/HACS-Integration
   einbinden und `custom_components/smart_homelab_maintenance/` installieren.
2. Die Karte im Lovelace-Karteneditor als `Smart Homelab Maintenance` auswählen.
3. Erst danach die Integration über den Config Flow mit einer privaten
   HTTPS-Agent-Adresse und vertrauenswürdiger Zertifikatskette verbinden.

Der spätere Proxmox-Installationsweg ist in
[`docs/AGENT_INSTALLATION.md`](docs/AGENT_INSTALLATION.md) beschrieben. Die
Skripte arbeiten standardmäßig nur im Prüfmodus und starten keinen Dienst.
Die vollständige Stable-Abnahme steht in
[`docs/STABLE_ACCEPTANCE.md`](docs/STABLE_ACCEPTANCE.md); sie ist eine
Prüfcheckliste und keine Installationsfreigabe.
Die passive Phase-29-Eignungs- und Aktivierungsmatrix steht in
[`docs/phase29-lxc-activation-matrix.md`](docs/phase29-lxc-activation-matrix.md);
auch sie aktiviert keinen Helper und keine Allowlist.

### Komponenten und Stable-Vorbereitung

HACS installiert die Home-Assistant-Integration und die Lovelace-Karte. Der
Proxmox-Agent ist ein getrennt laufender Dienst und muss aus demselben
geprüften Commit separat aktualisiert werden. Integration, Agent und API-
Vertrag werden deshalb vor jeder Freigabe getrennt geprüft. TLS, private
Netzwerkadressierung und die vertrauenswürdige Zertifikatskette sind
Voraussetzungen; HTTP-Fallback oder deaktivierte Zertifikatsprüfung sind nicht
zulässig. Installation, Upgrade und Rollback sind drei getrennte Vorgänge.

Für Stable werden zusätzlich der exakte Release-Tag, der offizielle Updater-
Preflight, Readiness, Dienstlebenszyklus, Rollback-Staging und die HACS-/HA-
Nachkontrolle dokumentiert. Der Agent-Updater arbeitet zunächst ohne Apply;
ein produktiver Apply und ein Dienstneustart benötigen eine eigene Freigabe.
Die aktuelle Funktion ist bewusst read-only: Host-Simulationen können nach
frischem Check freigegeben sein, LXC-Simulationen benötigen eine explizite
Allowlist/Helper-Einrichtung. VMs sind als dauerhafte Produktentscheidung von
Paketprüfung und Simulation ausgeschlossen; ihre Karten bleiben mit Name,
Laufstatus und Ressourcen sichtbar, zeigen aber den Hinweis „Updates dieser
virtuellen Maschine werden nicht über Smart Homelab Maintenance durchgeführt.
Bitte die Updatefunktion des jeweiligen Gastbetriebssystems verwenden.“ und
erreichen niemals einen Update-Runner. Echte Installationen bleiben deaktiviert.

The HACS package contains the Home Assistant integration and Lovelace card.
The Proxmox agent is a separate service and must be updated independently
from the same verified commit. Stable preparation therefore verifies the
integration, agent, API contract, TLS trust, updater preflight, readiness,
rollback staging, and post-update HA state separately. Installation, upgrade,
and rollback remain distinct operations. Host simulation is read-only; LXC
simulation requires explicit helper/allowlist authorization. VMs are
permanently excluded from package checks and simulations by product decision:
their cards still show name, runtime state, and resources, while the card
explains that updates must be performed by the guest operating system. VM
identifiers never reach `pct exec` or another update runner. Real installation
remains disabled.

Für eine spätere Veröffentlichung müssen die Marketplace-Struktur, die
Release-Artefakte und der Installationsweg erneut gegen die Zielversion von
Home Assistant geprüft werden. Jede Stable-Zeile muss mit PASS, BLOCKED oder
NOT RUN belegt sein; fehlende Nachweise werden nicht als Erfolg gewertet.

## Sicherheit

- passive Beta; keine Updateausführung
- keine freien Shell-Kommandos über die API
- Agent-Kommunikation nur über private HTTPS-Ziele, authentifiziert und
  größen-/timeoutbegrenzt
- unbekannte oder blockierte Anwendungen bleiben lesend
- Zugangsdaten gehören ausschließlich in die lokale Konfiguration und dürfen
  nicht in Logs, Issues, Screenshots oder Diagnosen erscheinen
- der Agent-Server erzwingt TLS, bindet nicht an unbeschränkte Adressen und
  nutzt getrennte systemd-Credentials; das Proxmox-Backend arbeitet nur lesend
- produktive Installation und Start sind nicht erfolgt

## Entwicklung und Tests

Die Tests verwenden Mock-Daten und lokale Fixtures. Details stehen in
`docs/architecture.md`, `docs/security.md` und `docs/testing.md`.

## Lizenz

MIT – Copyright (c) 2026 Michael Dick
