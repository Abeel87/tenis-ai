from __future__ import annotations

"""Deterministic semantic snapshot digests for audit/provenance joins."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SNAPSHOT_CONTRACT = "canonical-json-sha256-v1"


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stamp_report_results_snapshot(
    report_path: Path,
    results_path: Path,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    results = json.loads(results_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise TypeError("snapshot report must be a JSON object")
    if not isinstance(results, list):
        raise TypeError("results snapshot must be a JSON list")

    source = report.setdefault("source_snapshot", {})
    if not isinstance(source, dict):
        raise TypeError("report source_snapshot must be a JSON object")
    source["results_snapshot_contract"] = SNAPSHOT_CONTRACT
    source["results_snapshot_sha256"] = canonical_json_sha256(results)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("stamp-report",))
    parser.add_argument("report", type=Path)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    stamp_report_results_snapshot(args.report, args.results)


if __name__ == "__main__":
    main()
