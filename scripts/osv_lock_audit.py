#!/usr/bin/env python3
"""Fail-closed OSV fallback when npm's audit service is transiently unavailable."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"


def lock_packages(path: Path) -> list[tuple[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    found: set[tuple[str, str]] = set()
    for location, meta in (payload.get("packages") or {}).items():
        if "node_modules/" not in location or not isinstance(meta, dict):
            continue
        name = location.rsplit("node_modules/", 1)[-1].strip()
        version = str(meta.get("version") or "").strip()
        if name and version:
            found.add((name, version))
    return sorted(found)

def query_osv(packages: list[tuple[str, str]]) -> list[dict[str, Any]]:
    queries = [
        {"package": {"ecosystem": "npm", "name": name}, "version": version}
        for name, version in packages
    ]
    request = urllib.request.Request(
        OSV_BATCH_URL,
        data=json.dumps({"queries": queries}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "tenis-ai-ci-osv-fallback/1"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    results = payload.get("results") or []
    if len(results) != len(packages):
        raise RuntimeError("OSV querybatch result count mismatch")
    findings: list[dict[str, Any]] = []
    for (name, version), result in zip(packages, results):
        for vuln in (result or {}).get("vulns") or []:
            findings.append({"package": name, "version": version, "id": vuln.get("id")})
    return findings

def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    path = Path(args[0] if args else "package-lock.json")
    packages = lock_packages(path)
    if not packages:
        print("OSV_FALLBACK_ERROR no locked npm packages found", file=sys.stderr)
        return 2
    try:
        findings = query_osv(packages)
    except (OSError, urllib.error.URLError, ValueError, RuntimeError) as exc:
        print(f"OSV_FALLBACK_ERROR {exc}", file=sys.stderr)
        return 2
    if findings:
        print(json.dumps({"vulnerabilities": findings}, indent=2), file=sys.stderr)
        return 1
    print(f"OSV_FALLBACK_OK packages={len(packages)} vulnerabilities=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
