from __future__ import annotations

"""TASK 015: audit whether TML 2024 could safely improve current model readiness.

Audit-only. Four public TennisMyLife 2024 archives are downloaded into memory.
Nothing is written to the production cache and no model/runtime rule is changed.

Crucially, 2024 data is allowed to extend only player keys that already resolve
safely in the current baseline history. The preview therefore cannot introduce a
new identity, alias, fuzzy match, or provider-ID bridge. Current ``analyse_match``
is then run unchanged on baseline and preview histories to measure actual
match-level ``model_ready`` uplift (including minimum sample, quality and hold
probability gates), not merely a >=5 row upper bound.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import pandas as pd

try:
    from . import model, update
    from .history_coverage_audit import load_cached_history
    from .history_hygiene_v78a import clean_history
    from . import tml_2024_history_preview as task014
except ImportError:  # pragma: no cover
    import model, update
    from history_coverage_audit import load_cached_history
    from history_hygiene_v78a import clean_history
    import tml_2024_history_preview as task014


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "frontend" / "data" / "results.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "tml_2024_integration_readiness_audit.json"
VERSION = "task-015-tml-2024-integration-readiness-v1"
MIN_MATCHES = 5

IDENTITY_COLUMNS = ("tourney_date", "tourney_name", "winner_name", "loser_name", "score")
REQUIRED_MODEL_COLUMNS = (
    "tourney_date", "tourney_name", "surface", "winner_name", "loser_name", "score",
    "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon", "w_SvGms", "w_bpSaved", "w_bpFaced",
    "l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced",
)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _results_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("matches", [])
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _annotate(frame: pd.DataFrame, source: dict[str, str]) -> pd.DataFrame:
    out = frame.copy()
    out["source_tour"] = source["tour"]
    out["source_key"] = source["key"]
    return out


def _signature(row: pd.Series) -> tuple[str, ...]:
    values = []
    for column in IDENTITY_COLUMNS:
        value = row.get(column)
        values.append("" if pd.isna(value) else str(value).strip())
    return tuple(values)


def _signatures(frame: pd.DataFrame | None) -> set[tuple[str, ...]]:
    if frame is None or frame.empty:
        return set()
    return {_signature(row) for _, row in frame.iterrows()}


def _profile_key(profile: dict[str, Any], player: str) -> str | None:
    mode = str(profile.get("history_identity_mode") or "none")
    if mode in {"none", "ambiguous"}:
        return None
    stored = profile.get("history_player_key")
    if isinstance(stored, str) and stored.strip():
        return stored.strip()
    return model._core._key(player) if mode == "exact" else None


def _safe_baseline_keys(results: list[dict[str, Any]], baseline_long: pd.DataFrame) -> set[str]:
    keys: set[str] = set()
    for match in results:
        for side in ("p1", "p2"):
            player = str(match.get(side) or "").strip()
            if not player:
                continue
            key, mode = model._resolve_history_player_key(baseline_long, player)
            if key and mode not in {"none", "ambiguous"}:
                keys.add(str(key))
    return keys


def _schema_row(source: dict[str, str], frame: pd.DataFrame | None) -> dict[str, Any]:
    columns = set(frame.columns) if frame is not None else set()
    missing = [column for column in REQUIRED_MODEL_COLUMNS if column not in columns]
    coverage: dict[str, float] = {}
    if frame is not None and not frame.empty:
        for column in REQUIRED_MODEL_COLUMNS:
            coverage[column] = round(float(frame[column].notna().mean()), 4) if column in frame.columns else 0.0
    else:
        coverage = {column: 0.0 for column in REQUIRED_MODEL_COLUMNS}
    return {
        "key": source["key"],
        "tour": source["tour"],
        "rows": int(len(frame)) if frame is not None else 0,
        "required_columns_present": not missing,
        "missing_required_columns": missing,
        "required_column_non_null_fraction": coverage,
    }


def _clean_archives(archive_frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    annotated = []
    per_source = []
    for source in task014.TML_2024_SOURCES:
        raw = archive_frames.get(source["key"])
        per_source.append(_schema_row(source, raw))
        if raw is not None and not raw.empty:
            annotated.append(_annotate(raw, source))
    combined = pd.concat(annotated, ignore_index=True, sort=False) if annotated else pd.DataFrame()
    cleaned, hygiene = clean_history(combined)
    return cleaned, hygiene, per_source


def _build_identity_locked_preview_long(
    *,
    baseline_clean: pd.DataFrame,
    baseline_long: pd.DataFrame,
    archive_clean: pd.DataFrame,
    allowed_keys: set[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    baseline_sigs = _signatures(baseline_clean)
    archive_sigs = _signatures(archive_clean)
    overlap = baseline_sigs & archive_sigs

    if archive_clean is None or archive_clean.empty:
        return baseline_long.copy(), {
            "baseline_match_signatures": len(baseline_sigs),
            "archive_clean_match_signatures": 0,
            "archive_signatures_already_in_baseline": 0,
            "archive_net_new_match_signatures": 0,
            "archive_participant_rows_before_identity_lock": 0,
            "archive_participant_rows_after_identity_lock": 0,
        }

    keep_mask = archive_clean.apply(lambda row: _signature(row) not in baseline_sigs, axis=1)
    net_archive = archive_clean[keep_mask].copy()
    archive_long = model.normalize_matches(net_archive)
    before = int(len(archive_long))
    if not archive_long.empty and "player_key" in archive_long.columns:
        archive_long = archive_long[archive_long["player_key"].isin(allowed_keys)].copy()
    else:
        archive_long = archive_long.iloc[0:0].copy()

    preview = pd.concat([baseline_long, archive_long], ignore_index=True, sort=False)
    return preview, {
        "baseline_match_signatures": len(baseline_sigs),
        "archive_clean_match_signatures": len(archive_sigs),
        "archive_signatures_already_in_baseline": len(overlap),
        "archive_net_new_match_signatures": len(archive_sigs - baseline_sigs),
        "archive_participant_rows_before_identity_lock": before,
        "archive_participant_rows_after_identity_lock": int(len(archive_long)),
    }


def _side_snapshot(analysis: dict[str, Any], side: str) -> dict[str, Any]:
    player = str(analysis.get(side) or "")
    profile = analysis.get(f"{side}_stats") or {}
    return {
        "player": player,
        "history_key": _profile_key(profile, player),
        "identity_mode": str(profile.get("history_identity_mode") or "none"),
        "matches": int(profile.get("matches") or 0),
        "quality": str(profile.get("quality") or "LOW"),
        "data_confidence": profile.get("data_confidence"),
    }


def _audit_match(match: dict[str, Any], baseline_long: pd.DataFrame, preview_long: pd.DataFrame) -> dict[str, Any]:
    baseline = model.analyse_match(baseline_long, dict(match))
    preview = model.analyse_match(preview_long, dict(match))
    stored_ready = bool(match.get("model_ready"))
    baseline_ready = bool(baseline.get("model_ready"))
    preview_ready = bool(preview.get("model_ready"))

    sides = {}
    identity_stable = True
    for side in ("p1", "p2"):
        b = _side_snapshot(baseline, side)
        p = _side_snapshot(preview, side)
        stable = b["history_key"] == p["history_key"] and b["identity_mode"] == p["identity_mode"]
        identity_stable = identity_stable and stable
        sides[side] = {
            "baseline": b,
            "preview": p,
            "net_matches": p["matches"] - b["matches"],
            "identity_stable": stable,
            "crosses_minimum_5": b["matches"] < MIN_MATCHES <= p["matches"],
        }

    baseline_both_min5 = all(sides[side]["baseline"]["matches"] >= MIN_MATCHES for side in ("p1", "p2"))
    preview_both_min5 = all(sides[side]["preview"]["matches"] >= MIN_MATCHES for side in ("p1", "p2"))
    parity = stored_ready == baseline_ready
    return {
        "id": match.get("id"),
        "scheduled_time": match.get("scheduled_time"),
        "surface": match.get("surface"),
        "p1": match.get("p1"),
        "p2": match.get("p2"),
        "stored_model_ready": stored_ready,
        "baseline_recomputed_model_ready": baseline_ready,
        "preview_recomputed_model_ready": preview_ready,
        "baseline_runtime_parity": parity,
        "identity_stable": identity_stable,
        "baseline_both_minimum_5": baseline_both_min5,
        "preview_both_minimum_5": preview_both_min5,
        "new_both_minimum_5": (not baseline_both_min5) and preview_both_min5,
        "new_model_ready": (not baseline_ready) and preview_ready,
        "safe_new_model_ready": parity and identity_stable and (not stored_ready) and preview_ready,
        "sides": sides,
    }


def _task014_invariant_check(baseline_raw: pd.DataFrame, results: list[dict[str, Any]], archive_frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    report = task014.build_report(
        baseline_raw=baseline_raw,
        results=results,
        archive_frames=archive_frames,
    )
    anomalies = []
    for row in report.get("cases", []):
        baseline = int(row.get("baseline_clean_pre_match_rows") or 0)
        augmented = int(row.get("augmented_clean_pre_match_rows") or 0)
        expected = baseline < MIN_MATCHES <= augmented
        actual = bool(row.get("reaches_minimum_5"))
        if actual != expected:
            anomalies.append({
                "match_id": row.get("match_id"),
                "player": row.get("player"),
                "baseline": baseline,
                "augmented": augmented,
                "reported": actual,
                "expected": expected,
            })
    return {
        "short_history_cases": int(report.get("summary", {}).get("short_history_slots") or 0),
        "players_reaching_minimum_5": int(report.get("summary", {}).get("players_reaching_minimum_5") or 0),
        "invariant_anomalies": anomalies,
    }


def build_report(
    *,
    baseline_raw: pd.DataFrame,
    results: list[dict[str, Any]],
    archive_frames: dict[str, pd.DataFrame],
    source_status: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    baseline_clean, baseline_hygiene = clean_history(baseline_raw)
    baseline_long = model.normalize_matches(baseline_clean)
    allowed_keys = _safe_baseline_keys(results, baseline_long)

    archive_clean, archive_hygiene, schema = _clean_archives(archive_frames)
    preview_long, dedupe = _build_identity_locked_preview_long(
        baseline_clean=baseline_clean,
        baseline_long=baseline_long,
        archive_clean=archive_clean,
        allowed_keys=allowed_keys,
    )

    matches = [_audit_match(match, baseline_long, preview_long) for match in results]
    parity_mismatches = [row for row in matches if not row["baseline_runtime_parity"]]
    identity_anomalies = [row for row in matches if not row["identity_stable"]]
    new_both_min5 = [row for row in matches if row["new_both_minimum_5"]]
    new_ready = [row for row in matches if row["safe_new_model_ready"]]
    gain_matches = [
        row for row in matches
        if any(row["sides"][side]["net_matches"] > 0 for side in ("p1", "p2"))
    ]
    crossing_players = sorted({
        row["sides"][side]["preview"]["player"]
        for row in matches
        for side in ("p1", "p2")
        if row["sides"][side]["crosses_minimum_5"]
    })

    task014_check = _task014_invariant_check(baseline_raw, results, archive_frames)
    schema_ok = bool(schema) and all(row["required_columns_present"] for row in schema)
    all_sources = bool(source_status) and all(row.get("fetch_success") for row in source_status)
    readiness_evidence_clean = (
        all_sources
        and schema_ok
        and not parity_mismatches
        and not identity_anomalies
        and not task014_check["invariant_anomalies"]
    )

    categories = Counter()
    for row in matches:
        if row["safe_new_model_ready"]:
            categories["new_model_ready"] += 1
        elif row["new_both_minimum_5"]:
            categories["new_both_min5_but_not_model_ready"] += 1
        elif any(row["sides"][side]["net_matches"] > 0 for side in ("p1", "p2")):
            categories["history_gain_without_new_both_min5"] += 1
        else:
            categories["no_match_level_history_gain"] += 1

    return {
        "version": VERSION,
        "policy": {
            "live_tennis_api_calls": 0,
            "tennismylife_requests": len(task014.TML_2024_SOURCES),
            "production_cache_writes": 0,
            "temporary_or_memory_only": True,
            "fuzzy_matching": False,
            "manual_aliases": False,
            "provider_id_matching": False,
            "cross_provider_id_comparison": False,
            "uses_existing_baseline_identity_only": True,
            "minimum_match_gate": MIN_MATCHES,
            "minimum_match_gate_changed": False,
            "identity_resolver_changed": False,
            "history_hygiene_changed": False,
            "model_math_changed": False,
            "analyse_match_changed": False,
            "runtime_change_authorized": False,
            "archive_data_authorized_for_runtime": False,
        },
        "summary": {
            "visible_matches": len(results),
            "baseline_raw_rows": int(len(baseline_raw)),
            "baseline_clean_rows": int(len(baseline_clean)),
            "archive_clean_rows": int(len(archive_clean)),
            "safe_baseline_player_keys": len(allowed_keys),
            "preview_added_participant_rows": dedupe["archive_participant_rows_after_identity_lock"],
            "matches_with_any_history_gain": len(gain_matches),
            "players_crossing_minimum_5": len(crossing_players),
            "crossing_players": crossing_players,
            "matches_new_both_minimum_5": len(new_both_min5),
            "matches_new_model_ready": len(new_ready),
            "new_model_ready_match_ids": [row["id"] for row in new_ready],
            "baseline_runtime_parity_mismatches": len(parity_mismatches),
            "identity_stability_anomalies": len(identity_anomalies),
            "task014_invariant_anomalies": len(task014_check["invariant_anomalies"]),
            "all_2024_sources_fetched": all_sources,
            "all_sources_schema_compatible": schema_ok,
            "readiness_evidence_clean": readiness_evidence_clean,
        },
        "category_counts": dict(sorted(categories.items())),
        "dedupe": dedupe,
        "baseline_hygiene": baseline_hygiene,
        "archive_hygiene": archive_hygiene,
        "schema": schema,
        "sources": source_status or [],
        "task014_consistency": task014_check,
        "priority": {
            "new_model_ready": new_ready,
            "new_both_minimum_5_but_not_model_ready": [row for row in new_both_min5 if not row["safe_new_model_ready"]],
            "history_gain": gain_matches,
            "baseline_runtime_parity_mismatches": parity_mismatches,
            "identity_stability_anomalies": identity_anomalies,
        },
        "matches": matches,
        "decision": {
            "runtime_change": False,
            "authorize_2024_archive": False,
            "integration_readiness_evidence_clean": readiness_evidence_clean,
            "reason": (
                "TASK 015 measures compatibility and match-level readiness using the unchanged current model. "
                "Even clean positive evidence requires a separate reviewed integration change before 2024 may enter production history."
            ),
        },
    }


def run(
    *,
    results_path: Path = DEFAULT_RESULTS,
    output_path: Path = DEFAULT_OUTPUT,
    downloader: Callable[[str], pd.DataFrame] = update.download_csv,
) -> dict[str, Any]:
    baseline_raw = load_cached_history()
    results = _results_list(_read_json(results_path, []))
    archive_frames: dict[str, pd.DataFrame] = {}
    status: list[dict[str, Any]] = []
    for source in task014.TML_2024_SOURCES:
        try:
            frame = downloader(source["url"])
            if frame is None or frame.empty:
                raise RuntimeError("empty_csv")
            archive_frames[source["key"]] = frame
            status.append({
                "key": source["key"], "tour": source["tour"], "url": source["url"],
                "fetch_success": True, "rows": int(len(frame)), "error": None,
            })
        except Exception as exc:
            status.append({
                "key": source["key"], "tour": source["tour"], "url": source["url"],
                "fetch_success": False, "rows": 0, "error": type(exc).__name__,
            })

    report = build_report(
        baseline_raw=baseline_raw,
        results=results,
        archive_frames=archive_frames,
        source_status=status,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit TML 2024 integration readiness without runtime changes")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(results_path=args.results, output_path=args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps(report["category_counts"], ensure_ascii=False, indent=2, sort_keys=True))
    if not report["summary"]["all_2024_sources_fetched"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
