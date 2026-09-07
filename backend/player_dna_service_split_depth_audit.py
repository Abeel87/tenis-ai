from __future__ import annotations

"""Audit why canonical PBP service-split history is shallow.

This is diagnostic-only. It compares the current conservative rule (the latest
stats profile must match the final tape score) with the strictly safer question
"does any stats profile in the same PBP payload match the final tape score?".
It never changes profile selection, joins, training, scoring, or runtime.
"""

import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_pbp_service_split_readiness import (
        RAW_KEYS,
        SPLIT_FIELDS,
        _final_tape_score,
        _parse_utc,
        _ratio_counts,
        _score_core,
    )
    from backend.player_identity import player_identity_map
except ModuleNotFoundError:  # direct execution compatibility
    from player_dna_pbp_service_split_readiness import (
        RAW_KEYS,
        SPLIT_FIELDS,
        _final_tape_score,
        _parse_utc,
        _ratio_counts,
        _score_core,
    )
    from player_identity import player_identity_map

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT = ROOT / "frontend" / "data" / "player_dna_service_split_depth_audit.json"

VERSION = "player-dna-service-split-depth-audit-v1"
MODE = "SHADOW_DIAGNOSTIC_ONLY"


def _stats_profiles(payload: dict[str, Any]) -> list[tuple[datetime | None, int, dict[str, Any]]]:
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        return []
    out: list[tuple[datetime | None, int, dict[str, Any]]] = []
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict):
            continue
        state = profile.get("input_state")
        stats = state.get("stats") if isinstance(state, dict) else None
        if not isinstance(stats, dict):
            continue
        out.append((_parse_utc(profile.get("created_at")), index, profile))
    out.sort(
        key=lambda item: (
            item[0] is not None,
            item[0] or datetime.min.replace(tzinfo=timezone.utc),
            item[1],
        )
    )
    return out


def _profile_is_terminal(profile: dict[str, Any], final_score: tuple[str, str] | None) -> bool:
    if final_score is None:
        return False
    state = profile.get("input_state") if isinstance(profile.get("input_state"), dict) else {}
    return _score_core(state.get("score")) == final_score


def _profile_has_all_four_raw_both(profile: dict[str, Any]) -> bool:
    state = profile.get("input_state") if isinstance(profile.get("input_state"), dict) else {}
    stats = state.get("stats") if isinstance(state.get("stats"), dict) else {}
    for side in ("p1", "p2"):
        raw_side = stats.get(side) if isinstance(stats.get(side), dict) else {}
        for field in SPLIT_FIELDS:
            if _ratio_counts(raw_side.get(RAW_KEYS[field])) is None:
                return False
    return True


def inspect_snapshot_depth(payload: dict[str, Any]) -> dict[str, Any]:
    identities = player_identity_map(payload)
    profiles = _stats_profiles(payload)
    final_score = _final_tape_score(payload)
    latest = profiles[-1][2] if profiles else None
    terminal_profiles = [p for _, _, p in profiles if _profile_is_terminal(p, final_score)]
    terminal_raw = [p for p in terminal_profiles if _profile_has_all_four_raw_both(p)]

    return {
        "stable_identity": bool(identities),
        "stats_profile_count": len(profiles),
        "latest_is_terminal": bool(latest and _profile_is_terminal(latest, final_score)),
        "latest_has_all_four_raw_both": bool(latest and _profile_has_all_four_raw_both(latest)),
        "any_terminal_profile": bool(terminal_profiles),
        "terminal_profile_count": len(terminal_profiles),
        "any_terminal_all_four_raw_both": bool(terminal_raw),
        "terminal_all_four_raw_profile_count": len(terminal_raw),
        "latest_terminal_all_four_raw_both": bool(
            latest
            and _profile_is_terminal(latest, final_score)
            and _profile_has_all_four_raw_both(latest)
        ),
    }


def audit_payloads(payloads: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    profile_count_histogram = Counter()
    terminal_count_histogram = Counter()

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        counts["matches_seen"] += 1
        item = inspect_snapshot_depth(payload)
        counts["stable_identity_matches"] += int(item["stable_identity"])
        counts["matches_with_stats_profiles"] += int(item["stats_profile_count"] > 0)
        counts["latest_terminal_matches"] += int(item["latest_is_terminal"])
        counts["latest_terminal_all_four_raw_matches"] += int(item["latest_terminal_all_four_raw_both"])
        counts["matches_with_any_terminal_profile"] += int(item["any_terminal_profile"])
        counts["matches_with_any_terminal_all_four_raw"] += int(item["any_terminal_all_four_raw_both"])
        counts["recoverable_if_latest_rule_is_only_blocker"] += int(
            item["any_terminal_all_four_raw_both"]
            and not item["latest_terminal_all_four_raw_both"]
        )
        profile_count_histogram[str(min(int(item["stats_profile_count"]), 20))] += 1
        terminal_count_histogram[str(min(int(item["terminal_profile_count"]), 20))] += 1

    latest_raw = int(counts["latest_terminal_all_four_raw_matches"])
    any_terminal_raw = int(counts["matches_with_any_terminal_all_four_raw"])
    recoverable = int(counts["recoverable_if_latest_rule_is_only_blocker"])

    return {
        "version": VERSION,
        "mode": MODE,
        "contract": {
            "diagnostic_only": True,
            "canonical_profile_selection_changed": False,
            "historical_csv_namespace_used": False,
            "name_or_fuzzy_join_used": False,
            "stable_pbp_identity_required_for_future_use": True,
            "final_tape_score_required_for_terminal_evidence": True,
            "raw_numerator_denominator_required": True,
            "training_join_enabled": False,
            "scorer_activation_enabled": False,
            "runtime_activation_enabled": False,
        },
        "counts": dict(counts),
        "profile_count_histogram_capped_20": dict(sorted(profile_count_histogram.items(), key=lambda kv: int(kv[0]))),
        "terminal_profile_count_histogram_capped_20": dict(sorted(terminal_count_histogram.items(), key=lambda kv: int(kv[0]))),
        "comparison": {
            "current_latest_terminal_all_four_raw_matches": latest_raw,
            "any_terminal_all_four_raw_matches": any_terminal_raw,
            "potentially_recoverable_matches": recoverable,
            "recovery_multiplier": round(any_terminal_raw / latest_raw, 6) if latest_raw else None,
            "safe_selection_change_proven": False,
            "note": "Coverage evidence only. Any canonical selector change requires a separate explicit gate and tests.",
        },
    }


def iter_payloads(cache: Path = CACHE) -> Iterable[dict[str, Any]]:
    if not cache.exists():
        return
    for path in sorted(cache.glob("*.json.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            yield payload


def main() -> None:
    report = audit_payloads(iter_payloads())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    comparison = report["comparison"]
    print(
        "Service-split depth audit: "
        f"latest_raw={comparison['current_latest_terminal_all_four_raw_matches']} "
        f"any_terminal_raw={comparison['any_terminal_all_four_raw_matches']} "
        f"recoverable={comparison['potentially_recoverable_matches']} "
        f"multiplier={comparison['recovery_multiplier']}"
    )


if __name__ == "__main__":
    main()
