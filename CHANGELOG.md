# Changelog

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
