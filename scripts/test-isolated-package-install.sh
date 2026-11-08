#!/usr/bin/env bash
set -euo pipefail

# Real dpkg installation in a disposable root.  No host package database,
# repository, guest, VM, or network is touched.
ROOT="$(mktemp -d /tmp/smh-apt-root.XXXXXX)"
WORK="$(mktemp -d /tmp/smh-apt-package.XXXXXX)"
cleanup() { rm -rf -- "$ROOT" "$WORK"; }
trap cleanup EXIT

mkdir -p "$ROOT/var/lib/dpkg" "$ROOT/var/log" "$WORK/pkg/DEBIAN" "$WORK/pkg/usr/share/smh-e2e"
: > "$ROOT/var/lib/dpkg/status"
cat > "$WORK/pkg/DEBIAN/control" <<'EOF'
Package: smh-e2e-fixture
Version: 1.0
Architecture: all
Maintainer: Smart Homelab Maintenance
Description: disposable update acceptance fixture
EOF
printf '%s\n' 'fixture-v1' > "$WORK/pkg/usr/share/smh-e2e/version"
dpkg-deb --build "$WORK/pkg" "$WORK/smh-e2e-fixture_1.0_all.deb" >/dev/null
dpkg --root="$ROOT" --admindir="$ROOT/var/lib/dpkg" --instdir="$ROOT" -i "$WORK/smh-e2e-fixture_1.0_all.deb" >/dev/null
grep -qx 'fixture-v1' "$ROOT/usr/share/smh-e2e/version"

sed -i 's/^Version: 1.0$/Version: 2.0/' "$WORK/pkg/DEBIAN/control"
printf '%s\n' 'fixture-v2' > "$WORK/pkg/usr/share/smh-e2e/version"
dpkg-deb --build "$WORK/pkg" "$WORK/smh-e2e-fixture_2.0_all.deb" >/dev/null
dpkg --root="$ROOT" --admindir="$ROOT/var/lib/dpkg" --instdir="$ROOT" -i "$WORK/smh-e2e-fixture_2.0_all.deb" >/dev/null
grep -qx 'fixture-v2' "$ROOT/usr/share/smh-e2e/version"
dpkg-query --root="$ROOT" --admindir="$ROOT/var/lib/dpkg" -W -f='${Version}\n' smh-e2e-fixture | grep -qx '2.0'
printf '%s\n' 'PASS: isolated real package install and upgrade in disposable dpkg root'
