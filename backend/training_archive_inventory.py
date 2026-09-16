from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = ROOT / "data" / "cache"
DEFAULT_OUTPUT = ROOT / "artifacts" / "training_archive_inventory.json"
SCHEMA_VERSION = 1

PBP_MATCH_PREFIX = "pbp_v7/matches/"
PBP_STATE_PATHS = {
    "pbp_v7/players.json",
    "pbp_v7/terminal_refresh.json",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_path(relative_path: str) -> tuple[str, bool, str | None]:
    """Classify cache content without changing any producer or training logic.

    Only hard-to-reproduce raw inputs and the minimal PBP lookup state are archive
    candidates. Everything else remains a rebuildable Actions cache concern.
    """
    rel = relative_path.replace("\\", "/").lstrip("./")

    if rel.startswith(PBP_MATCH_PREFIX) and rel.endswith(".json.gz"):
        return "pbp_match_raw", True, "live_tennis_api"

    if rel in PBP_STATE_PATHS:
        return "pbp_state", True, "live_tennis_api_index"

    if rel.endswith(".csv.gz") and not rel.startswith("pbp_v7/"):
        return "historical_csv_raw", True, "historical_csv_upstream"

    return "rebuildable_cache", False, None


def _candidate_entry(path: Path, cache_root: Path) -> dict[str, Any]:
    rel = path.relative_to(cache_root).as_posix()
    category, archive_candidate, provider = classify_path(rel)
    if not archive_candidate:
        raise ValueError(f"not an archive candidate: {rel}")
    return {
        "logical_path": rel,
        "class": category,
        "provider": provider,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build_inventory(cache_root: Path) -> dict[str, Any]:
    cache_root = Path(cache_root)
    files = sorted((p for p in cache_root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(cache_root).as_posix()) if cache_root.exists() else []

    total_bytes = 0
    rebuildable_bytes = 0
    rebuildable_files = 0
    class_counts: Counter[str] = Counter()
    class_bytes: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []

    for path in files:
        rel = path.relative_to(cache_root).as_posix()
        size = path.stat().st_size
        total_bytes += size
        category, archive_candidate, _provider = classify_path(rel)
        class_counts[category] += 1
        class_bytes[category] += size
        if archive_candidate:
            candidates.append(_candidate_entry(path, cache_root))
        else:
            rebuildable_files += 1
            rebuildable_bytes += size

    by_digest: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in candidates:
        by_digest[entry["sha256"]].append(entry)

    unique_candidate_bytes = 0
    duplicate_groups = 0
    duplicate_files = 0
    dedupe_savings_bytes = 0
    for entries in by_digest.values():
        if not entries:
            continue
        size = int(entries[0]["size_bytes"])
        unique_candidate_bytes += size
        if len(entries) > 1:
            duplicate_groups += 1
            duplicate_files += len(entries) - 1
            dedupe_savings_bytes += size * (len(entries) - 1)

    candidate_bytes = sum(int(entry["size_bytes"]) for entry in candidates)
    classes = {
        name: {"files": int(class_counts[name]), "bytes": int(class_bytes[name])}
        for name in sorted(class_counts)
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "policy": {
            "archive_raw_only": True,
            "content_addressing": "sha256",
            "runtime_bucket_reuse": False,
        },
        "summary": {
            "total_cache_files": len(files),
            "total_cache_bytes": total_bytes,
            "archive_candidate_files": len(candidates),
            "archive_candidate_bytes": candidate_bytes,
            "unique_archive_objects": len(by_digest),
            "unique_archive_bytes": unique_candidate_bytes,
            "duplicate_groups": duplicate_groups,
            "duplicate_files": duplicate_files,
            "dedupe_savings_bytes": dedupe_savings_bytes,
            "rebuildable_files": rebuildable_files,
            "rebuildable_bytes": rebuildable_bytes,
            "classes": classes,
        },
        "archive_candidates": candidates,
    }


def _write_summary(inventory: dict[str, Any], summary_path: Path | None) -> None:
    if summary_path is None:
        return
    summary = inventory["summary"]
    lines = [
        "## Durable training archive inventory",
        "",
        "Inventory only — no Supabase archive objects were written.",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Cache files | {summary['total_cache_files']} |",
        f"| Cache bytes | {summary['total_cache_bytes']} |",
        f"| Archive candidates | {summary['archive_candidate_files']} |",
        f"| Candidate bytes | {summary['archive_candidate_bytes']} |",
        f"| Unique candidate bytes | {summary['unique_archive_bytes']} |",
        f"| SHA-256 dedupe savings | {summary['dedupe_savings_bytes']} |",
        f"| Rebuildable bytes | {summary['rebuildable_bytes']} |",
        "",
        "### Classes",
        "",
    ]
    for name, values in summary["classes"].items():
        lines.append(f"- `{name}`: {values['files']} files / {values['bytes']} bytes")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory durable training inputs in data/cache")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-candidates", action="store_true")
    args = parser.parse_args()

    inventory = build_inventory(args.cache_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    _write_summary(inventory, Path(github_summary) if github_summary else None)

    print(json.dumps(inventory["summary"], sort_keys=True))
    if args.require_candidates and inventory["summary"]["archive_candidate_files"] <= 0:
        raise SystemExit("no durable training archive candidates found in restored cache")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
