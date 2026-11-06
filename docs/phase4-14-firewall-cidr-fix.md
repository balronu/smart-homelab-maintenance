# Phase 4.14 – CIDR-Korrektur der Firewall-Persistenz

## Ergebnis

Der Fehler aus Phase 4.13 wurde im gemeinsamen Firewall-Helfer korrigiert.
Die Korrektur ist vollständig isoliert getestet. Produktive Firewall-Regeln,
systemd-Units und Dienste wurden in dieser Phase nicht verändert.

**NO-GO für eine erneute produktive Aktivierung in dieser Phase.**
Nach erfolgreicher CI und einer neuen ausdrücklichen Freigabe ist ein erneuter
kontrollierter Aktivierungsversuch technisch vorbereitet.

## 1. Fehlerursache

`iptables-save` gibt eine einzelne IPv4-Adresse als Hostnetz mit `/32` aus.
Die frühere Prüfung suchte dagegen die Textfolge ohne CIDR-Suffix und bewertete
eine korrekte Regel als Konflikt.

## 2. Korrektur

`scripts/agent-firewall-common.sh` normalisiert jetzt semantisch mit
Python-`ipaddress`:

- `A.B.C.D` und `A.B.C.D/32` gelten als dieselbe einzelne Hostadresse;
- ein `/24`-Netz wird nicht als Hostadresse akzeptiert;
- ungültige CIDR-Werte werden abgelehnt;
- Quell- und Zieladresse müssen exakt den konfigurierten Hosts entsprechen;
- Allow-Regeln müssen TCP/48128 und `ACCEPT` enthalten;
- Drop-Regeln müssen TCP/48128 und `DROP` ohne Quell-/Zielrestriktion enthalten;
- doppelte eigene Regeln werden abgelehnt;
- eine Drop-Regel vor der Allow-Regel wird abgelehnt;
- fremde Tailscale-Regeln bleiben unberücksichtigt und unverändert.

## 3. Geänderte Dateien

- `scripts/agent-firewall-common.sh`
- `tests/test_firewall_scripts.py`
- `docs/phase4-14-firewall-cidr-fix.md`

## 4. Regressionstests

Die Tests berücksichtigen den tatsächlichen `iptables-save`-Stil und prüfen:

- Hostadresse ohne CIDR;
- Hostadresse mit `/32`;
- abweichende Einzeladresse;
- zu breites `/24`-Netz;
- ungültige CIDR-Angabe;
- doppelte eigene Regeln;
- falsche Allow/Drop-Reihenfolge;
- vorhandene Tailscale-Regeln;
- IPv6-Sperre;
- Apply-Bestätigung und Dry-Run;
- isolierte Wiederholungsanwendung ohne neue Regeln;
- isolierte Rücknahme ausschließlich eigener Regeln.

## 5. Testergebnisse

| Prüfung | Ergebnis |
|---|---|
| Shell-Syntax | PASSED |
| Firewall-Regressionstests | PASSED – 7 Tests |
| Core-/Backend-Tests | PASSED – 30 Tests |
| Gesamt lokal | **37/37 PASSED** |
| Isolierte Wiederholungs-/Rücknahmesimulation | PASSED |
| Produktive Firewalländerung | NOT RUN – ausdrücklich verboten |
| systemd-Installation/Aktivierung | NOT RUN – ausdrücklich verboten |

Die bereits aktiven produktiven Agent-Regeln wurden nicht verändert. Die
fehlgeschlagene Persistenzinstallation aus Phase 4.13 bleibt zurückgenommen.

## 6. CI und GitHub

Die Korrektur wird im bestehenden PR #2 geprüft. Merge und Release erfolgen
nicht in dieser Phase. Der endgültige CI-Status wird nach dem Push des Fixes
direkt im PR verifiziert.

## 7. Freigabeentscheidung

**GO für die technische Vorbereitung eines späteren kontrollierten Versuchs**
nach erfolgreicher vollständiger CI und neuer ausdrücklicher Freigabe.

**NO-GO für jede produktive Aktivierung jetzt.** Die Phase endet ohne
Installation, Aktivierung oder Neustart.
