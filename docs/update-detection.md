# Passive update detection / Passive Update-Erkennung

## Deutsch

Die Updateprüfung ist passiv: Sie verwendet ausschließlich bereits
vorhandene Paketinformationen und führt weder `apt update` noch Installation,
Upgrade oder einen produktiven Dry Run aus. Der einzige zugelassene
Simulationsbefehl ist der serverseitig feste APT-Simulationspfad; echte
Updateausführung bleibt standardmäßig deaktiviert; der separate Beta.34-Pfad
kann nur mit eigener Update-Berechtigung und expliziter Bestätigung aktiv
werden.

### Statuswerte

| Status | Bedeutung |
|---|---|
| `updates_available` | Paketupdates wurden erkannt; Anzahl und Pakete werden geliefert. |
| `current` | Die Prüfung lief erfolgreich und meldet keine Updates. |
| `not_checked` | Für das Ziel liegt noch keine Prüfung vor, etwa bei einer VM ohne Gastzugriff. |
| `unsupported` | OS/Paketmanager oder Gastzugriff sind nicht nachgewiesen. |
| `unauthorized` | Das Ziel ist nicht für die Prüfung freigegeben. |
| `error` | Die Prüfung ist mit einem technischen Fehler fehlgeschlagen. |
| `stale` | Das Ergebnis ist älter als die erlaubte Aktualitätsdauer. |
| `unknown` | Der Zustand konnte nicht sicher klassifiziert werden. |

Proxmox kann die Paketmanager und Betriebssysteme innerhalb eines Gasts nicht
aus der normalen LXC-/VM-Inventarantwort ableiten. Deshalb bleiben LXC und VM
ohne ausdrücklich autorisierte Gast-Metadaten `unsupported` bzw. `not_checked`;
das ist nicht gleichbedeutend mit „keine Updates“.

Für eine spätere, ausdrücklich freigegebene Gastprüfung kann der Agent eine
Allowlist in seiner TOML-Konfiguration erhalten:

```toml
[update_targets."container:107"]
simulation_authorized = true
update_authorized = false
os_name = "Debian"
os_version = "12"
package_manager = "apt"
```

Die Allowlist akzeptiert nur Ziel-ID, Freigabe, OS-Name/-Version und den festen
Paketmanager. Sie akzeptiert keine Shell-Befehle, Pfade oder Credentials. Die
Konfiguration wird in Beta.19 nicht produktiv geändert.

Ein Dry-Run-Button erscheint nur bei einem frischen erfolgreichen Ergebnis mit
`updates_available` und `dry_run_supported=true`. Der Installationsbutton wird
nur bei `update_supported=true`, frischem Plan und Digest aktiv; die UI kann
keine Berechtigung erzeugen.

## English

Beta.19 update detection is passive. It uses existing package information only
and never runs `apt update`, installation, upgrade, or a productive dry run.
The only permitted simulation is the fixed server-side APT simulation path;
real update execution remains disabled.

The API preserves explicit states: `updates_available`, `current`,
`not_checked`, `unsupported`, `unauthorized`, `error`, `stale`, and `unknown`.
Unknown must never be interpreted as up to date. Proxmox inventory does not
prove a guest OS or package manager, so LXCs remain `unsupported` and VMs
without authorized guest access are returned as `not_checked`.

An explicit, separately approved target allowlist may provide Debian/Ubuntu and
APT metadata later. It cannot provide commands, paths, or credentials. The
Beta.19 UI exposes a dry-run button only for a fresh successful update result;
the server-side prohibition on real execution is unchanged.
