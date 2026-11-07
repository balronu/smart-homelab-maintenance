# Changelog

## 0.1.0-beta.24 – Kanonischer Dry-Run-Planvergleich (Prerelease)

### Deutsch

- Normalisiert Paketpläne vor dem Digest-Vergleich; reine Reihenfolgeänderungen
  zwischen APT-Cache und Simulation lösen keinen falschen Stale-Abbruch mehr aus.
- Behält den sicheren Abbruch bei echten Planänderungen unverändert bei.
- Zeigt unbekannte Speicherwerte nicht mehr als 0 % und übersetzt fehlenden
  Gastzugriff verständlich.
- Stabilisiert das responsive Aktionslayout ohne Installationspfad.

### English

- Canonicalizes package plans before digest comparison so source ordering alone
  no longer causes a false stale-plan rejection.
- Keeps the safety abort for real plan changes unchanged.
- Does not render unknown memory values as 0% and localizes missing guest access.
- Stabilizes the responsive action layout without adding an installation path.

## 0.1.0-beta.23 – Dry-Run-Serviceauswahl (Kandidat)

### Deutsch

- Behebt den Fehler, bei dem `dry_run` ohne `entry_id` ein internes
  Setup-Flag als Coordinator verwendete und dadurch mit
  `bool has no attribute transport` abbrach.
- Ergänzt Regressionen für erfolgreiche Antworten, HTTP-/TLS-Fehler,
  Zeitüberschreitungen und ungültige Ziele.
- Zeigt die Simulationsaktion für Host, VMs und LXCs immer an; nicht
  autorisierte oder nicht unterstützte Ziele bleiben sichtbar und deaktiviert.
- Zeigt die dauerhaft deaktivierte Installationsaktion einheitlich und
  responsiv neben beziehungsweise unter der Simulation an und übersetzt
  Autorisierungsfehler ins Deutsche.
- Der Service bleibt `SupportsResponse.ONLY`; echte Updates bleiben
  serverseitig deaktiviert.

### English

- Fixes `dry_run` without `entry_id` selecting an internal setup flag as the
  coordinator, which caused `bool has no attribute transport`.
- Adds regressions for successful responses, HTTP/TLS errors, timeouts, and
  invalid targets.
- Keeps the simulation action visible for hosts, VMs, and LXCs while disabling
  unauthorized or unsupported targets with a clear reason.
- Keeps the permanently disabled install action in a consistent responsive
  layout and localizes authorization errors in German.
- The service remains `SupportsResponse.ONLY`; real updates remain disabled
  server-side.

## 0.1.0-beta.22 – sicherer Agent-Preflight (Prerelease)

### Deutsch

- Erkennt eindeutig historische Rollback-Staging-Stände und lässt sie
  unverändert bestehen.
- Blockiert weiterhin aktive, ungültige oder mehrdeutige Upgrade-Zustände.
- Wählt den Rollback-Stand beim Austausch anhand der zuvor aktiven Version
  statt anhand einer zufälligen Verzeichnisreihenfolge.
- Keine produktive Agent-, HA- oder LXC-Änderung durch dieses Release.

### English

- Recognizes provably historical rollback staging and preserves it unchanged.
- Continues to block active, invalid, or ambiguous upgrade states.
- Selects the rollback state by the previously active version instead of an
  arbitrary directory order during an update.
- This release makes no productive agent, HA, or LXC changes.

## 0.1.0-beta.21 – sicherer LXC-Gastzugriff (Prerelease)

### Deutsch

- Root-seitiger Helper für strikt allowlistete, passive LXC-APT-Lese-
  und Dry-Run-Operationen dokumentiert und mit Sicherheitsregressionen
  abgesichert.
- Socket-Clients werden per `SO_PEERCRED` auf die exakte Agent-UID begrenzt;
  Allowlist, Request, Prozesslaufzeit und Ausgabe werden pro Anfrage begrenzt
  und geprüft.
- Keine produktive Installation, sudoers-Änderung oder Allowlist-Aktivierung;
  echte Updateausführung bleibt deaktiviert.

### English

- Added a root-side helper candidate for tightly allowlisted, passive LXC APT
  reads and simulations, with security regression coverage.
- Unix-socket clients are restricted to the exact agent UID via `SO_PEERCRED`;
  allowlist, requests, process lifetime, and output are bounded per request.
- No production installation, sudoers change, or allowlist activation; real
  update execution remains disabled.

## Unreleased – Agent-Updater Readiness und Rollback

### Deutsch

- Der Agent-Updater wartet nach dem Dienststart innerhalb eines begrenzten
  Zeitfensters auf einen TLS-validierten Healthcheck mit passender Version und
  API 1.1.
- Fehlerpfade verwenden einen EXIT-sicheren Rollback; der fehlerhafte Code
  bleibt zur Diagnose erhalten und vorhandenes Rollback-Staging wird nicht
  automatisch gelöscht.

### English

- The agent updater now waits within a bounded window for a TLS-validated
  health response with the expected version and API 1.1.
- Failure paths use EXIT-safe rollback; failed code remains available for
  diagnosis and existing rollback staging is never deleted automatically.

## 0.1.0-beta.19 – Dry-Run-Serviceantwort und Update-Erkennung (Prerelease)

### Deutsch

- Fordert die verpflichtende Home-Assistant-Serviceantwort für
  `smart_homelab_maintenance.dry_run` korrekt an.
- Zeigt Simulationsergebnis, Paketänderungen, Warnungen, Sicherheitsbewertung,
  leere Antworten, Servicefehler und Zeitüberschreitungen in der Karte an.
- Keine echten Updates, keine automatische Freigabe und keine produktiven
  Änderungen.
- Bewahrt eindeutige Zustände der passiven Update-Erkennung und macht
  `unsupported`, `not_checked`, `unauthorized`, `error`, `stale` und `unknown`
  in API und Karte sichtbar.
- Erlaubt spätere Gast-Allowlist-Metadaten nur für feste Ziel-IDs, OS-/Versions-
  und Paketmanagerangaben; Befehle, Pfade und Credentials bleiben ausgeschlossen.

### English

- Correctly requests the mandatory Home Assistant service response for
  `smart_homelab_maintenance.dry_run`.
- Displays simulation results, package changes, warnings, safety assessment,
  empty responses, service errors, and timeouts in the card.
- No real updates, automatic approval, or productive changes are enabled.
- Preserves explicit passive update states and displays `unsupported`,
  `not_checked`, `unauthorized`, `error`, `stale`, and `unknown` in the API and
  card.
- Future guest allowlist metadata is limited to fixed target IDs, OS/version,
  and package-manager fields; commands, paths, and credentials are excluded.

Beta.19 is published as a GitHub prerelease. HACS updates the Home Assistant
integration and card only; the separately running agent requires its own
reviewed, explicitly approved update process. No productive agent or guest
system was changed by this release.

## 0.1.0-beta.18 – gemeinsamer Versions- und Updatevertrag

- DE: Integration, Lovelace-Karte und Agent melden eine gemeinsame Version und
  einen expliziten API-Vertrag. Abweichungen werden als aktuell, veraltet,
  inkompatibel oder unbekannt angezeigt. Der Agent-Updateprozess ist
  ausdrücklich bestätigt, transaktional und nach dem Healthcheck rückrollbar;
  echte Systemupdates bleiben deaktiviert.
- EN: Integration, Lovelace card, and agent expose one coordinated version plus
  an explicit API contract. Mismatches are shown as current, outdated,
  incompatible, or unknown. Agent updates require explicit confirmation, use a
  transactional health-checked path, and can roll back; real system updates
  remain disabled.

## 0.1.0-beta.17 – Ressourcen- und Agent-Vertrag (Prerelease)

### Deutsch

- Ergänzt `agent_version` im öffentlichen Healthcheck, damit HA-Integration
  und separat laufender Wartungsagent auf denselben Beta-Stand geprüft werden
  können.
- Korrigiert die Proxmox-Projektion: fehlende CPU-/RAM-/Speicherwerte bleiben
  unbekannt statt als `0` zu erscheinen; erfolgreiche API-Erreichbarkeit wird
  nicht wegen fehlender optionaler Messwerte als Host-offline bewertet.
- Bewahrt die funktionierenden LXC-Freiwerte und trennt sie von VM-Werten,
  für die Proxmox keine Gast-Dateisystem- oder Gast-RAM-Freimessung liefert.
- Verdichtet die Karte mit beschrifteten CPU-, RAM- und Speicherbalken. Freie
  RAM-/Speicherwerte stehen direkt am jeweiligen Balken; fehlende Daten blenden
  den Balken aus.
- Keine echte Updateausführung, keine Paketinstallation und kein produktiver
  Zugriff. Beta.17 bleibt read-only; ein echter iPhone-Praxistest bleibt
  erforderlich.
- Für die neuen Ressourcenwerte müssen Integration und separat laufender Agent
  gemeinsam auf Beta.17 stehen; ein reines HACS-Update aktualisiert den Agenten
  nicht.

### English

- Adds `agent_version` to the public health response so the HA integration and
  separately running maintenance agent can be checked for the same beta line.
- Fixes Proxmox projection: missing CPU, RAM, and storage values remain
  unknown instead of becoming fabricated zeroes; successful API reachability
  is not reported as host offline because optional metrics are absent.
- Preserves working LXC free-resource values and separates them from VM
  values when Proxmox does not provide guest filesystem or guest-RAM free data.
- Makes the card more compact with labelled CPU, RAM, and storage bars. Free
  RAM/storage values appear beside the relevant bar; missing data hides the bar.
- No real update execution, package installation, or productive access. Beta.17
  remains read-only; a real iPhone field test is still required.
- The integration and separately running agent must both be on Beta.17 for the
  new resource fields; a HACS update alone does not update the agent.

## 0.1.0-beta.16 – Fehlerisolierung für Update-Abfragen (Prerelease)

### Deutsch

- Behebt einen Beta.15-Fehler, bei dem ein HTTP-Fehler der optionalen
  `/api/v1/updates`-Abfrage Host-, VM- und LXC-Daten komplett ausblendete.
- Führt Update-Abfragen getrennt vom Kerninventar aus; bei einem Fehler bleiben
  die Bestandsdaten sichtbar und der Updatezustand wird als unbekannt gemeldet.
- Behebt den von Home Assistant 2026.11 gemeldeten thread-unsicheren Aufruf
  von `hass.async_create_task` im Intervall-Callback.
- Echte Updateausführung bleibt serverseitig deaktiviert; Dry Runs bleiben die
  einzige erlaubte Aktionsstufe.
- Der iPhone-Scrollfix ist weiterhin nicht durch einen echten iOS-Praxistest
  bestätigt.

### English

- Fixes a Beta.15 regression where an HTTP error from the optional
  `/api/v1/updates` request hid all host, VM, and LXC inventory data.
- Runs update polling separately from core inventory; when it fails, inventory
  remains visible and the update state is reported as unknown.
- Fixes the thread-unsafe `hass.async_create_task` call in the interval
  callback reported by Home Assistant 2026.11.
- Real update execution remains server-disabled; dry runs remain the only
  permitted action level.
- The iPhone scroll fix is still not confirmed by a real iOS field test.

## 0.1.0-beta.15 – Sichere Update-Prüfung und Simulation (Kandidat)

### Deutsch

- Ergänzt passive Update-Erkennung für den Proxmox-Host und autorisierte
  Debian-/Ubuntu-LXC-Ziele über einen festen, begrenzten APT-Prüfpfad.
- Zeigt `aktuell`, `Updates verfügbar`, `unbekannt`, `nicht unterstützt` und
  Fehler getrennt; fehlende Messwerte werden nicht erfunden.
- Ergänzt einen ausdrücklich bestätigten Dry Run mit
  `apt-get --simulate --no-remove upgrade`. Paketindex-Aktualisierung,
  Installation, Entfernung und Neustarts finden nicht statt.
- Die Ausführung echter Updates ist serverseitig deaktiviert; die spätere
  Freischaltung muss zusätzlich aktuellen Dry Run, unveränderten Plan,
  Konflikt-/Entfernungsprüfung und ausdrückliche Bestätigung erzwingen.
- Beta.15 ist ein Releasekandidat. Der iPhone-Scrollfix bleibt ohne echten
  iOS-Praxistest unbestätigt.

### English

- Adds passive update detection for the Proxmox host and authorized
  Debian/Ubuntu LXC targets through a fixed, bounded APT inspection path.
- Distinguishes up to date, updates available, unknown, unsupported, and error;
  missing measurements are never fabricated.
- Adds an explicitly confirmed dry run using
  `apt-get --simulate --no-remove upgrade`. It does not refresh indexes,
  install or remove packages, or restart services.
- Real update execution is server-disabled. Any later enablement must enforce
  a current dry run, unchanged plan, conflict/removal checks, and explicit
  confirmation server-side.
- Beta.15 is a release candidate. The iPhone scroll fix remains unverified
  without a real iOS field test.

## 0.1.0-beta.14 – Sections-Resize- und Ressourcen-Kandidat

### Deutsch

- Meldet Änderungen der tatsächlichen Kartenhöhe über `ResizeObserver` als
  `card-updated`, damit Home Assistants Sections-Wrapper nach dem Öffnen von
  Detailbereichen neu layouten können.
- Ergänzt eine Sections-Fixture, die einen veralteten Wrapper-Höhenwert und
  das abgeschnittene Kartenende reproduziert; CT112 muss im reparierten Pfad
  erreichbar bleiben.
- Reicht CPU-, RAM-, Speicher- und Laufzeitfelder des read-only Proxmox-
  Backends bis zu den HA-Entitätsattributen durch.
- Die iPhone-Praxisbehebung bleibt unbestätigt; diese Version ist nur ein
  Kandidat und wurde nicht veröffentlicht oder produktiv installiert.

### English

- Reports actual card-size changes through `ResizeObserver` as `card-updated`,
  allowing Home Assistant Sections wrappers to re-layout after details open.
- Adds a Sections fixture reproducing stale wrapper height and clipped card
  endings; CT112 must remain reachable in the fixed path.
- Preserves CPU, RAM, storage, and uptime fields from the read-only Proxmox
  backend through to Home Assistant entity attributes.
- The iPhone fix remains unverified; this is a candidate only and was neither
  published nor installed in production.

## 0.1.0-beta.13 – Next Generation Dashboard (Kandidat)

- Modernisiert die read-only Lovelace-Karte mit klarer Statusübersicht,
  responsiven Kartenbreiten und aufklappbaren VM-/LXC-Details.
- Entfernt die wirkungslose `min_rows`-Angabe neben `rows: "auto"`; die Karte
  meldet weiterhin volle Sections-Breite und folgt ausschließlich ihrem Inhalt.
- Bewahrt DOM-Identität, offene Details, Fokus und Scrollposition bei HA-Updates.
- Erweitert die Browser-Regressionen um 0, 1, 10, 20 und 50 Container sowie
  erreichbare Kartenenden in simulierten Sections-/Masonry-Layouts.
- Kein produktiver Home-Assistant-/Proxmox-Zugriff und keine Veröffentlichung.

## 0.1.0-beta.11 – Lovelace-Scrollstabilität (Prerelease-Kandidat)

- Verhindert unnötiges Entfernen und Wiedereinfügen bestehender VM-/LXC-Karten
  bei gewöhnlichen `hass`-Aktualisierungen.
- Ergänzt Regressionen für Scrollposition, DOM-Identität, Grid-Mutationen,
  Fokus, äußeren Kartenbaum und drei unabhängige Karteninstanzen.
- Vollständige Browser-Matrix für iPhone-, iPad- und Desktop-Viewports sowie
  Home-Assistant-Runtime- und HACS-Prüfungen bleiben erforderlich.
- Kein automatischer Home-Assistant-Neustart, keine Installation und keine
  Änderungen an Proxmox oder dem Agenten.

## 0.1.0-beta.9 – Mobile Kartenstabilität (Kandidat)

- Bewahrt den geöffneten Proxmox-Hostbereich über mehrere Home-Assistant-
  Statusupdates hinweg.
- Ermittelt das responsive Kartenraster anhand der tatsächlichen Kartenbreite:
  eine, zwei oder bis zu drei Spalten.
- Bricht lange VM-/LXC-Namen sicher um und begrenzt Status-Badges auf mobilen
  Ansichten.
- Blendet unbekannte OS-Werte aus, statt `unknown unknown` anzuzeigen, und
  entfernt die doppelte Read-only-Anzeige.
- Ergänzt Regressionen für wiederholte `hass`-Updates, lange Namen und
  unbekannte Sensorwerte.

## 0.1.0-beta.8 – Lovelace-Entitätsdaten und Status (Kandidat)

- Erkennt VMs und LXC-Container anhand ihrer tatsächlichen Attribute und nicht
  nur anhand historischer Entity-ID-Präfixe.
- Zeigt vorhandene freie Ressourcenwerte an, ohne fehlende CPU-, RAM- oder
  Speicherwerte zu simulieren.
- Trennt Agent-Verbindung, Hostzustand sowie unbekannte/offline Fehlerzustände.
- Ergänzt Regressionen mit anonymisierten Live-Entitätsstrukturen.

## 0.1.0-beta.7 – Robuste Lovelace-Spracherkennung (Kandidat)

- Behebt den iPhone-Editorfehler `locale?.toLowerCase is not a function`.
- Verwendet eine zentrale, typgeprüfte Sprachauflösung mit Priorität für
  `hass.language`, sicherer Unterstützung von `hass.locale` als String oder
  Objekt und englischem Fallback.
- Ergänzt Regressionen für Karte, Vorschau, Editor, fehlendes `hass` sowie
  deutsche und englische Sprachwerte.

## 0.1.0-beta.6 – Lovelace editor layout and preview fix (Candidate)

- Add responsive editor layout with localized German/English labels.
- Preserve card preview sizing and render an explicit offline/empty state.
- Add a Home Assistant editor-contract harness for picker, preview, save, and
  reopen lifecycle coverage.

## 0.1.0-beta.5 – Lovelace mobile editor fix (Candidate)

- Keep the editor DOM stable during `setConfig()` updates so mobile focus and
  unsaved input survive Home Assistant background updates.
- Add iPhone/iPad Playwright coverage for empty/unknown entities, browser errors,
  failed requests, and the editor lifecycle.

## 0.1.0-beta.4 – Lovelace-Dashboard (Prerelease)

- Read-only Lovelace-Karte für Proxmox-Host, VMs, LXC-Container und
  Wartungshinweise ergänzt.
- Host-, VM- und LXC-Messwerte werden aus den tatsächlich vorhandenen HA-
  Entitäten erkannt; fehlende Daten werden nicht simuliert.
- Karte wird beim Laden der Integration automatisch als versionierte
  Frontend-Ressource registriert und ist über den grafischen Karteneditor
  auswählbar.
- Responsive Light-/Dark-Mode-Darstellung und deutsche/englische Texte ergänzt.
- Als GitHub-Prerelease veröffentlicht; eine produktive Installation ist nicht
  erfolgt.

## 0.1.0-beta.3 – Private HTTPS-IP-Transport (lokaler Kandidat)

- Private HTTPS-Ziele einschließlich IP-Adressen mit aktivierter
  Zertifikats- und IP-SAN-Prüfung unterstützt.
- CA-Dateien sind auf `/ssl/` begrenzt; HTTP- und unsichere TLS-Fallbacks bleiben
  ausgeschlossen.
- Nicht veröffentlicht und nicht in produktivem Home Assistant installiert.

## Unreleased – Phase 4.6 Agent-Runtime

- lesender Proxmox-HTTPS-Client für Host, LXC und VMs mit TLS-, Größen- und
  Authentifizierungsprüfung
- TOML-basierter Agent-Startpunkt mit getrennten systemd-Credentials und
  read-only Runtime-Verdrahtung
- Installer um Proxmox-URL, CA, Knoten und geschütztes API-Credential ergänzt
- Update- und Shell-Ausführung bleibt deaktiviert

## Unreleased – Phase 4.4 Vorbereitung

- Read-only Proxmox-Inventory-Backend mit injizierbarem Client für LXC und VMs
- TLS-erzwingender Agent-Server mit Bearer-Authentifizierung und systemd-
  Credential-Laden vorbereitet
- Keine Update- oder Shell-Ausführung ergänzt; produktiver Listener bleibt
  unimplementiert/ungeinstalliert

## Unreleased – Phase 4.5 Installer-Vorbereitung

- reproduzierbare Installations-, Prüf-, Update- und Deinstallationsskripte
- exakte Commit-Prüfung, TLS-/DNS-Gates und geschützte systemd-Credentials
- standardmäßig kein Apply, kein Start und kein automatischer Neustart

## 0.1.0-beta.2 – Config-Flow-Fix

- Config Flow funktioniert als eigenständiges Home-Assistant-Paket ohne das
  separate Agent-Paket.
- HTTP-Transport innerhalb der Integration gebündelt; keine unzulässigen
  Laufzeitimporte aus `agent`.
- Regressionstest für den isolierten Installationsfall ergänzt.
- Passive Beta bleibt read-only; Updateausführung bleibt deaktiviert.

## 0.1.0-beta.1 – Passive Beta

- Read-only Home-Assistant-Integration, Agent-Kern und Lovelace-Karte
- Offline-Discovery, API-Verträge, Jobverwaltung und Sicherheitsgates
- Updateausführung global deaktiviert
- Installation der Karte aus derselben Version als lokale HA-Ressource
- Keine produktive Geräte- oder Infrastrukturaktion
## 0.1.0-beta.10 – Scroll- und DOM-Stabilität (Prerelease veröffentlicht)

- Behebt den iPhone-Scrollsprung durch einmaligen Shadow-DOM-Aufbau und
  inkrementelle Updates bestehender Knoten.
- Bewahrt aufgeklappte Hostbereiche sowie die DOM-Identität von VM- und
  Containerkarten während wiederholter `hass`-Aktualisierungen.
- Ergänzt eine reproduzierbare Scroll-Regression mit drei unabhängigen
  Karteninstanzen sowie iPhone-, iPad- und Desktop-Browser-Matrix.
- Keine automatische Installation, kein HA-Neustart und keine Änderungen an
  Proxmox oder Agent.
## 0.1.0-beta.19 – passive update status clarity (candidate)

### Deutsch

- Unterscheidet `unsupported`, `unauthorized`, `not_checked`, `error`,
  `stale`, `current` und `updates_available` im API-Vertrag und in der Karte.
- Ergänzt eine eng begrenzte, optionale Allowlist für ausdrücklich autorisierte
  Debian-/Ubuntu-APT-Gastziele; sie verändert keine produktive Konfiguration.
- Zeigt Updateanzahl, Sicherheitsupdates, Prüfzeitpunkt und Fehler verständlich
  an. Ungeprüfte oder nicht unterstützte Ziele werden nicht als aktuell bewertet.
- Beta.19 enthält weiterhin keine echte Updateausführung und keine automatische
  Paketlistenaktualisierung.

### English

- Preserves explicit update states in the API and Lovelace card instead of
  collapsing unsupported, unauthorized, not-checked, error, and stale results
  into one generic label.
- Adds a tightly allowlisted opt-in format for explicitly authorized
  Debian/Ubuntu APT guest targets without changing production configuration.
- Displays update counts, security updates, check time, and errors clearly.
- Real update execution and automatic package-index refresh remain disabled.
## 0.1.0-beta.20 – Updateverwaltung ohne Ausführung

### Deutsch

- Passive Update-Erkennung liest ausschließlich vorhandene APT-Cache-Daten;
  der ausdrücklich angeforderte Dry Run bleibt ein getrennt validierter Pfad.
- LXC-Ziele sind standardmäßig nicht autorisiert; nur eine explizite Allowlist
  kann ein laufendes Debian-/Ubuntu-Ziel freigeben. Gestoppte Container werden
  nicht gestartet oder angesprochen.
- Paketname sowie installierte und verfügbare Versionen werden angezeigt;
  Sicherheitsklassifizierungen bleiben unbekannt, wenn die Datenquelle sie
  nicht belastbar liefert.
- Der sichtbare Button „Updates installieren“ ist dauerhaft deaktiviert und
  serverseitig nicht implementiert.

### English

- Passive update detection reads existing APT cache data only; the explicitly
  requested dry run remains a separate, validated path.
- LXC targets are unauthorized by default; only an explicit allowlist can
  authorize a running Debian/Ubuntu target. Stopped containers are never
  started or probed.
- Package names and installed/available versions are exposed; security
  classification remains unknown when the source cannot prove it.
- The visible “Install updates” button is permanently disabled and has no
  server-side execution route.
## 0.1.0-beta.25 – Agent-Lifecycle und Port-Bind-Race (Prerelease)

### Deutsch

- Der externe Agent beendet seinen HTTPS-Server bei `SIGTERM`/`SIGINT` jetzt
  kontrolliert und schließt den Listen-Socket garantiert.
- Der Updater prüft nach dem Dienststopp die tatsächliche Freigabe von Port
  48128, bevor der Agent-Baum ausgetauscht oder ein neuer Prozess gestartet
  wird. Ein belegter Port bricht sicher ab.
- `TimeoutStopSec=30` begrenzt den systemd-Stopp; historische und fehlgeschlagene
  Rollback-Stagings bleiben erhalten.

## Nächster Beta-Kandidat – Port-Bind-Forensik

### Deutsch

- Der Updater prüft für Port 48128 neben `LISTEN` auch aktive TCP-Zustände und
  bestätigt, dass die systemd-Unit tatsächlich inaktiv ist. Der terminale,
  kernelverwaltete `TIME-WAIT`-Zustand wird bei `SO_REUSEADDR` nicht als
  blockierender Listener behandelt.
- Vor und nach Stopp, Swap und Start werden ausschließlich nicht-sensitive
  MainPID-, ControlPID-, Cgroup- und Socketdaten protokolliert.
- Die vorhandenen Journale beweisen den wiederholten Bind-Fehler, aber nicht
  mehr nachträglich die historische Halter-PID. Diese Unsicherheit bleibt
  ausdrücklich dokumentiert.

### English

- Before swapping the agent tree, the updater checks all TCP states for port
  48128, not only `LISTEN`, and confirms that the systemd unit is inactive.
- Non-sensitive MainPID, ControlPID, cgroup, and socket diagnostics are logged
  around stop, swap, and start.
- Existing journals prove the repeated bind failure but cannot recover the
  historical holder PID after the fact; that uncertainty is documented.

### English

- The external agent now shuts down its HTTPS server explicitly on
  `SIGTERM`/`SIGINT` and always closes the listening socket.
- After stopping the service, the updater verifies that port 48128 is really
  free before swapping the agent tree or starting a new process. A still-busy
  port causes a safe abort.
- `TimeoutStopSec=30` bounds the systemd stop; historical and failed rollback
  staging directories remain preserved.
## 0.1.0-beta.26 – Port-Gate-Forensik und sichere Upgrade-Rennen (Prerelease)

### Deutsch

- Der Updater blockiert aktive TCP-Zustände und eine noch aktive systemd-Unit
  auf Port 48128; ausschließlich der terminale, kernelverwaltete `TIME-WAIT`
  Zustand wird bei `SO_REUSEADDR` ausgenommen.
- Eine zweite Port-/Unit-Prüfung unmittelbar vor `systemctl start` schließt das
  Stop-/Swap-/Start-Rennen. PID-, ControlPID-, Cgroup- und Socket-Diagnose wird
  nicht-sensitiv an den relevanten Übergängen protokolliert.
- Die isolierten Regressionen decken freien Port, Listener, verzögerten
  Shutdown, Doppelstart und `TIME-WAIT` ab. Beta.24-Planvergleich und Beta.25-
  Lifecycle-Fix bleiben enthalten; Rollback-Schutz und gesperrte produktive
  Updatepfade bleiben unverändert.

### English

- The updater blocks active TCP states and an active systemd unit on port 48128;
  only terminal kernel-owned `TIME-WAIT` is exempted for the server's
  `SO_REUSEADDR` bind.
- A second port/unit check immediately before `systemctl start` closes the
  stop/swap/start race. PID, ControlPID, cgroup, and socket diagnostics remain
  non-sensitive at the relevant transitions.
- Isolated regressions cover a free port, active listener, delayed shutdown,
  duplicate start, and `TIME-WAIT`. The Beta.24 plan comparison and Beta.25
  lifecycle fix remain included; rollback protection and locked production
  update paths are unchanged.
