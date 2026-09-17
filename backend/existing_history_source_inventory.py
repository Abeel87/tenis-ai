from __future__ import annotations

"""TASK 011: inventory every restored cache file for independent history sources.

This is diagnostic only. It never performs provider requests and never authorizes a
new history source. Known archive candidates are classified through the existing
training-archive policy; rebuildable material is inspected structurally only to
flag raw-like files for a later provenance audit.
"""

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .training_archive_inventory import classify_path
except ImportError:  # pragma: no cover
    from training_archive_inventory import classify_path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "data" / "cache"
DEFAULT_OUTPUT = ROOT / "artifacts" / "existing_history_source_inventory.json"
VERSION = "task-011-existing-history-source-inventory-v1"
MAX_INSPECT_BYTES = 8 * 1024 * 1024

KNOWN_HISTORY_PROVIDERS = {
    "historical_csv_upstream": "tennismylife",
    "live_tennis_api": "live_tennis_api_pbp",
    "live_tennis_api_index": "live_tennis_api_pbp_state",
}

RAW_MATCH_KEYSETS = (
    frozenset(("winner_name", "loser_name", "tourney_date", "score")),
    frozenset(("p1", "p2", "scheduled_time", "result")),
    frozenset(("player1", "player2", "date", "score")),
    frozenset(("home", "away", "date", "score")),
)


def _role_for_rebuildable(rel: str) -> str:
    low = rel.casefold()
    name = Path(rel).name.casefold()
    if name == "manifest.json":
        return "cache_manifest"
    if any(token in low for token in ("state", "cursor", "quota", "refresh", "backfill", "priority")):
        return "state_or_scheduler"
    if any(token in low for token in ("model", "rank", "elo", "feature", "prediction", "result")):
        return "derived_or_model_cache"
    if low.endswith((".sqlite", ".sqlite3", ".db")):
        return "local_database_unproven"
    if low.endswith((".json", ".json.gz", ".csv", ".csv.gz")):
        return "structured_unproven"
    return "other_rebuildable"


def _sample_dicts(value: Any, limit: int = 200) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    stack = [value]
    while stack and len(out) < limit:
        item = stack.pop()
        if isinstance(item, dict):
            out.append(item)
            for child in list(item.values())[:30]:
                if isinstance(child, (dict, list)):
                    stack.append(child)
        elif isinstance(item, list):
            for child in item[:100]:
                if isinstance(child, (dict, list)):
                    stack.append(child)
    return out


def _load_structured(path: Path) -> Any | None:
    try:
        if path.stat().st_size > MAX_INSPECT_BYTES:
            return None
        if path.name.endswith(".json.gz"):
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                return json.load(handle)
        if path.suffix.casefold() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _raw_like_shape(path: Path) -> tuple[bool, list[str]]:
    value = _load_structured(path)
    if value is None:
        return False, []
    matched: set[str] = set()
    for row in _sample_dicts(value):
        keys = frozenset(str(key) for key in row)
        for required in RAW_MATCH_KEYSETS:
            if required.issubset(keys):
                matched.add("+".join(sorted(required)))
    return bool(matched), sorted(matched)


def build_inventory(cache_root: Path) -> dict[str, Any]:
    cache_root = Path(cache_root)
    files = sorted(
        (path for path in cache_root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(cache_root).as_posix(),
    ) if cache_root.exists() else []

    classes: Counter[str] = Counter()
    providers: Counter[str] = Counter()
    rebuildable_roles: Counter[str] = Counter()
    rebuildable_rows: list[dict[str, Any]] = []
    raw_like_unproven: list[dict[str, Any]] = []
    known_raw_rows: list[dict[str, Any]] = []

    for path in files:
        rel = path.relative_to(cache_root).as_posix()
        category, archive_candidate, provider = classify_path(rel)
        classes[category] += 1
        size = int(path.stat().st_size)
        if archive_candidate:
            provider_name = KNOWN_HISTORY_PROVIDERS.get(str(provider), str(provider or "unknown"))
            providers[provider_name] += 1
            known_raw_rows.append({
                "logical_path": rel,
                "class": category,
                "provider": provider_name,
                "size_bytes": size,
            })
            continue

        role = _role_for_rebuildable(rel)
        rebuildable_roles[role] += 1
        raw_like, shapes = _raw_like_shape(path)
        row = {
            "logical_path": rel,
            "role": role,
            "size_bytes": size,
            "raw_match_shape_detected": raw_like,
            "raw_match_shapes": shapes,
        }
        rebuildable_rows.append(row)
        if raw_like:
            raw_like_unproven.append(row)

    independent_provider_families = sorted({row["provider"] for row in known_raw_rows if row["class"] != "pbp_state"})
    third_known_provider_families = [
        provider for provider in independent_provider_families
        if provider not in ("tennismylife", "live_tennis_api_pbp")
    ]

    return {
        "version": VERSION,
        "policy": {
            "network_calls": 0,
            "provider_requests": 0,
            "production_cache_writes": 0,
            "runtime_change_authorized": False,
            "history_source_authorized": False,
            "minimum_match_gate_changed": False,
            "identity_resolver_changed": False,
            "model_math_changed": False,
            "raw_like_is_not_proven_raw": True,
        },
        "summary": {
            "cache_files": len(files),
            "known_archive_candidate_files": len(known_raw_rows),
            "rebuildable_files": len(rebuildable_rows),
            "known_independent_provider_families": len(independent_provider_families),
            "third_known_provider_families": len(third_known_provider_families),
            "raw_like_unproven_files": len(raw_like_unproven),
        },
        "class_counts": dict(sorted(classes.items())),
        "provider_counts": dict(sorted(providers.items())),
        "rebuildable_role_counts": dict(sorted(rebuildable_roles.items())),
        "independent_provider_families": independent_provider_families,
        "third_known_provider_families": third_known_provider_families,
        "raw_like_unproven": raw_like_unproven,
        "rebuildable_files": rebuildable_rows,
        "decision": {
            "runtime_change": False,
            "authorize_new_history_source": False,
            "reason": "Inventory only. Any raw-like rebuildable file requires separate producer/provenance validation before player-level coverage is considered.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory restored cache for independent history sources")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_inventory(args.cache_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    print(json.dumps(report["rebuildable_role_counts"], sort_keys=True))
    for row in report["raw_like_unproven"]:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    if report["policy"]["network_calls"] != 0 or report["decision"]["runtime_change"]:
        return 2
    if report["summary"]["cache_files"] <= 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
