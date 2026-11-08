# Smart Homelab Maintenance

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
Home Assistant geprüft werden.

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
