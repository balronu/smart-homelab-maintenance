#!/usr/bin/env python3
"""Create and verify an in-content proof for a pre-release-identity rollback tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
from pathlib import Path

SCHEMA = 1
EVIDENCE_NAME = ".legacy-rollback-evidence.json"


def manifest(root: Path) -> tuple[str, int]:
    rows: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative == EVIDENCE_NAME:
            continue
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"Symlink im Legacy-Rollbackbaum: {relative}")
        if stat.S_ISREG(mode):
            rows.append(f"F {hashlib.sha256(path.read_bytes()).hexdigest()} {relative}")
        elif not stat.S_ISDIR(mode):
            raise ValueError(f"Nicht unterstützter Dateityp im Legacy-Rollbackbaum: {relative}")
    payload = "\n".join(rows) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), len(rows)


def create(root: Path) -> dict[str, object]:
    evidence_path = root / EVIDENCE_NAME
    if evidence_path.exists() or evidence_path.is_symlink():
        raise ValueError("Legacy-Rollback-Nachweis existiert bereits")
    if (root / ".release-identity").exists() or (root / ".release-identity").is_symlink():
        raise ValueError("Legacy-Nachweis ist für einen Baum mit Release-Identität nicht zulässig")
    digest, file_count = manifest(root)
    evidence = {
        "schema": SCHEMA,
        "kind": "legacy-rollback-evidence",
        "release_identity": None,
        "manifest_sha256": digest,
        "tree_sha256": digest,
        "file_count": file_count,
    }
    evidence_path.write_text(json.dumps(evidence, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.chmod(0o644)
    return evidence


def verify(root: Path) -> str:
    evidence_path = root / EVIDENCE_NAME
    identity_path = root / ".release-identity"
    if identity_path.exists() or identity_path.is_symlink():
        raise ValueError("Legacy-Nachweis und Release-Identität dürfen nicht gemeinsam vorhanden sein")
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Legacy-Rollback-Nachweis fehlt oder ist ungültig") from exc
    if (
        evidence.get("schema") != SCHEMA
        or evidence.get("kind") != "legacy-rollback-evidence"
        or evidence.get("release_identity") is not None
        or not isinstance(evidence.get("manifest_sha256"), str)
        or not isinstance(evidence.get("tree_sha256"), str)
        or evidence.get("manifest_sha256") != evidence.get("tree_sha256")
        or not isinstance(evidence.get("file_count"), int)
    ):
        raise ValueError("Legacy-Rollback-Nachweis ist nicht fail-closed verifizierbar")
    digest, file_count = manifest(root)
    if digest != evidence["manifest_sha256"] or file_count != evidence["file_count"]:
        raise ValueError("Legacy-Rollback-Manifest stimmt nicht mit dem Baum überein")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", action="store_true")
    group.add_argument("--verify", action="store_true")
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    try:
        result = create(args.root) if args.create else {"manifest_sha256": verify(args.root)}
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
