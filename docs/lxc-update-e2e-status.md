# LXC-Update-E2E-Status / Status of the LXC update E2E

## Deutsch

Beta.39 ist **nicht** die vollständige technische Abnahme der LXC-
Updateverwaltung. Der produktive CT110-Nachweis umfasst nur Read und Dry-Run;
`execution_enabled=false` bleibt unverändert.

Die CI enthält zusätzlich zwei getrennte Nachweise:

1. einen isolierten `dpkg`-Installations-/Upgrade-Test in einem temporären
   Paketroot;
2. einen festen Helper-Transporttest. Dieser ruft den unveränderten Helper-
   Vertrag mit einem numerischen LXC-ID-Transport-Fixture auf und führt im
   Wegwerf-Gastroot eine echte `dpkg`-Installation und ein Upgrade aus.

Der zweite Test weist **nicht** nach, dass Proxmox `pct` oder ein echter LXC-
Gast funktioniert. Für die abschließende Definition of Done ist ein ausdrücklich
als Test markierter, nichtproduktiver Proxmox-LXC erforderlich. Der Test muss
über den installierten Unix-Socket und den echten `pct status`/`pct exec`-
Transport laufen. Bis dieser Testgast verfügbar ist, darf kein Release als
vollständig E2E-abgenommen bezeichnet werden.

## English

Beta.39 is **not** the complete technical acceptance of LXC update management.
The productive CT110 evidence covers read and dry-run only; `execution_enabled=false`
remains unchanged.

CI now contains two separate proofs:

1. an isolated `dpkg` install/upgrade test in a temporary package root;
2. a fixed helper transport test. It invokes the unchanged helper contract with
   a numeric LXC-ID transport fixture and performs a real `dpkg` install and
   upgrade in a disposable guest root.

The second test does **not** prove that Proxmox `pct` or a real LXC guest works.
The final definition of done requires an explicitly designated, non-production
Proxmox LXC test guest. That test must use the installed Unix socket and the
real `pct status`/`pct exec` transport. Until then, no release may be described
as fully E2E-accepted.
