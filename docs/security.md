# Phase 2.2 – Sicherheitskonzept

Die lesende API verlangt außer beim minimalen Healthcheck ein Bearer-Token,
begrenzt Antworten und Logs und akzeptiert nur GET-Routen des festen v1-
Vertrags. Query-Parameter werden streng numerisch validiert. Zugangsdaten
werden weder in Discovery-Details noch in API-Antworten ausgegeben.

- Updateziele stammen ausschließlich aus der Adapter-Allowlist.
- API-Payloads lehnen unbekannte Felder, ungültige IDs, unbekannte Operationen,
  überlange Versionen und commandartige Zeichenfolgen ab.
- Freie Shell-Kommandos, `pct`, SSH, Netzwerkzugriff und Prozesse sind im Kern
  nicht vorhanden.
- Execution ist standardmäßig deaktiviert; die einzige Execution-Grenze wirft
  in Phase 2.1 immer `ExecutionDisabledError`.
- Eine partielle SQLite-Unique-Index-Sperre erlaubt pro Ziel höchstens einen
  aktiven Job. Idempotency-Keys sind global eindeutig.
- Speicher-, RAM-, Thin-Pool- und optional Swap-Grenzen werden vor einer
  späteren Ausführung als Gate ausgewertet.
- Logwerte werden rekursiv nach Secret-Schlüsseln gefiltert und auf eine
  begrenzte Länge gekürzt.
- Nach Neustart wird kein Job als erfolgreich fortgesetzt; Recovery ist
  erforderlich.

Die Ausführung benötigt in einer späteren Phase eine separate Freigabe,
prozessgebundene Berechtigungen, feste Wrapper und ein eigenes Security Review.

## Beta.21 LXC-Helper-Grenze

Der Beta.21-Kandidat enthält einen opt-in root-seitigen Helper für LXC-APT-
Metadaten. Er ist keine allgemeine `pct`- oder Root-Schnittstelle:

- Der Unix-Socket ist fest unter
  `/run/smart-homelab-maintenance/lxc-apt-helper.sock` gebunden, root-owned und
  auf die Agent-Gruppe begrenzt (`0660`). Zusätzlich wird jede Verbindung mit
  `SO_PEERCRED` auf die exakte UID `smart-homelab-maintenance` geprüft.
- Die Allowlist wird bei jeder Anfrage aus einer root-owned, nicht durch Gruppe
  oder andere beschreibbaren TOML-Datei geladen. Eine frühere, veraltete oder
  manipulierte Prozesskopie kann dadurch keine alte Freigabe weiterverwenden.
- Zulässig sind nur numerische allowlistete CT-IDs und die Operationen `read`
  (`apt list --upgradable`) sowie `simulate` (`apt-get --simulate --no-remove
  ... upgrade`). Es gibt keine freien Argumente, Pfade, Shell-Interpolation,
  `apt update`, Installation, Entfernung oder Neustartoperation.
- Vor `pct exec` wird der Containerstatus geprüft. Ein Stop-Race zwischen
  Statusprüfung und `pct exec` wird als Fehler behandelt; es gibt keinen
  automatischen Start und der feste Gastargv bleibt ohne Schreiboperation.
- Socket-Anfragen, Gastprozesse und Ausgaben sind begrenzt. Langsame Clients
  laufen in einen definierten Timeout; Gastprozesse werden bei Timeout oder
  256-KiB-Ausgabelimit beendet und die Pipes geschlossen.
- `lxc_helper_enabled` muss ein echtes TOML-Boolean sein und bleibt standardmäßig
  `false`. Stringwerte wie `"false"` aktivieren den Helper nicht versehentlich.

Die Grenze ist bis zu einer separaten produktiven Freigabe nicht installiert,
die Allowlist bleibt inaktiv, und echte Paketupdates bleiben serverseitig
gesperrt. Tests müssen weiterhin unautorisierte UIDs, CT-IDs, Operationen,
Status-Races, Zeitüberschreitungen, Ausgabelimits und fehlerhafte Gastantworten
abdecken.
