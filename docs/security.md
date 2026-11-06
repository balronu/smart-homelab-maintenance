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
