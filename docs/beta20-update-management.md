# Beta.20 – Updateverwaltung ohne Ausführung

## Deutsch

Beta.20 trennt drei Zustände, die zuvor vermischt werden konnten:

1. **Passive Erkennung:** Der Agent liest mit dem festen Aufruf
   `apt list --upgradable` den bereits vorhandenen APT-Cache. Es gibt kein
   `apt update`, keinen Paketdownload und keine Installation. Paketnamen sowie
   installierte und verfügbare Versionen werden nur aus dieser Antwort gelesen.
2. **Simulation:** Ein Benutzerklick auf „Update simulieren“ ruft den bereits
   geschützten Dry-Run-Service mit verpflichtender Response-Anforderung auf.
   Der Service verwendet ausschließlich den festen APT-Simulationsmodus und
   prüft, dass der Plan seit der passiven Prüfung unverändert ist.
3. **Ausführung:** Die Server-API enthält weiterhin keinen ausführbaren
   Updatepfad. Der sichtbare Button „Updates installieren“ ist deaktiviert,
   sendet keinen Serviceaufruf und bleibt auch nach einem erfolgreichen Dry Run
   deaktiviert.

### Zielstatus

- `updates_available`: Pakete aus dem vorhandenen Cache sind erkennbar.
- `current`: Der Cache meldet keine ausstehenden Pakete.
- `not_checked`: Ziel ist bekannt, aber ohne nachgewiesenen Gastzugriff oder
  nicht in einem für die Prüfung geeigneten Zustand.
- `unsupported`: Betriebssystem/Paketmanager ist nicht sicher Debian/Ubuntu +
  APT.
- `unauthorized`: Ziel steht nicht in der expliziten Server-Allowlist.
- `error`: Die zugelassene Prüfung ist fehlgeschlagen.
- `stale`: Das erfolgreiche Ergebnis ist älter als die definierte Gültigkeit.
- `unknown`: Status oder Datenquelle sind nicht bestimmbar.

Sicherheitsupdates werden nur gezählt, wenn die Antwort sie belastbar
klassifiziert. Ein fehlender Sicherheitsmarker wird nicht als „0“ erfunden.

## Allowlist und Zielinventar

Die zehn bekannten LXCs bleiben ohne ausdrücklich geprüfte Gastmetadaten
`unauthorized` oder `unsupported`; es wird keine produktive Allowlist aktiviert.
VM 104 (Home Assistant OS) und VM 106 (Proxmox Backup Server) bleiben ohne
autorisierten Gastweg `not_checked`. Der Proxmox-Host darf separat geprüft
werden, wenn sein APT-Cache und die Agent-Berechtigung vorhanden sind.

Eine spätere Freigabe muss pro CT-ID Betriebssystem, Version, Paketmanager,
Laufstatus und Berechtigung festlegen. Befehle, Pfade, Credentials und freie
Ziele sind nicht Bestandteil der Allowlist. Gestoppte LXCs dürfen nicht
automatisch gestartet werden.

## English

Beta.20 separates passive cache inspection, an explicitly requested dry run,
and update execution. Passive checks use only the fixed `apt list --upgradable`
command and never refresh indexes. The dry run remains response-bound and
plan- freshness checked. Update execution is not implemented server-side; the
visible install button is permanently disabled and has no service call.

The explicit status model is `updates_available`, `current`, `not_checked`,
`unsupported`, `unauthorized`, `error`, `stale`, and `unknown`. Security counts
are emitted only when the source provides a reliable classification.
