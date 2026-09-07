from __future__ import annotations

"""Audit why canonical PBP service-split history is shallow.

This module is diagnostic-only. It first tests whether the current conservative
selector (latest stats profile must match the final tape score) is the depth
bottleneck, then decomposes the remaining loss into three observable stages:

1. no stats profile captured,
2. stats exist but no single snapshot has all four raw split ratios for both
   players,
3. all-four raw evidence exists, but no all-four snapshot has terminal score
   proof against the final tape.

Nothing here changes canonical profile selection, identity joins, training,
scoring, runtime, Symfonia, or Superbet PLAYABLE.
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

VERSION = "player-dna-service-split-depth-audit-v2"
MODE = "SHADOW_DIAGNOSTIC_ONLY"

RAW_SLOTS = tuple(
    f"{side}_{field}"
    for side in ("p1", "p2")
    for field in SPLIT_FIELDS
)


def _stats_profiles(
    payload: dict[str, Any],
) -> list[tuple[datetime | None, int, dict[str, Any]]]:
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


def _profile_score(profile: dict[str, Any]) -> tuple[str, str] | None:
    state = (
        profile.get("input_state")
        if isinstance(profile.get("input_state"), dict)
        else {}
    )
    return _score_core(state.get("score"))


def _profile_is_terminal(
    profile: dict[str, Any],
    final_score: tuple[str, str] | None,
) -> bool:
    if final_score is None:
        return False
    return _profile_score(profile) == final_score


def _profile_raw_slots(profile: dict[str, Any]) -> set[str]:
    state = (
        profile.get("input_state")
        if isinstance(profile.get("input_state"), dict)
        else {}
    )
    stats = state.get("stats") if isinstance(state.get("stats"), dict) else {}
    present: set[str] = set()
    for side in ("p1", "p2"):
        raw_side = stats.get(side) if isinstance(stats.get(side), dict) else {}
        for field in SPLIT_FIELDS:
            if _ratio_counts(raw_side.get(RAW_KEYS[field])) is not None:
                present.add(f"{side}_{field}")
    return present


def _profile_has_all_four_raw_both(profile: dict[str, Any]) -> bool:
    return len(_profile_raw_slots(profile)) == len(RAW_SLOTS)


def _score_gap_kind(
    profiles: list[dict[str, Any]],
    final_score: tuple[str, str] | None,
) -> str:
    if not profiles:
        return "no_stats_profile"
    if final_score is None:
        return "missing_final_tape_score"

    scores = [score for score in (_profile_score(p) for p in profiles) if score]
    if not scores:
        return "no_parseable_profile_score"
    if any(score == final_score for score in scores):
        return "exact_terminal_present"

    any_sets_match = any(score[0] == final_score[0] for score in scores)
    any_games_match = any(score[1] == final_score[1] for score in scores)
    if any_sets_match and any_games_match:
        return "components_match_across_different_profiles_only"
    if any_sets_match:
        return "sets_match_games_differ"
    if any_games_match:
        return "games_match_sets_differ"
    return "sets_and_games_differ"


def inspect_snapshot_depth(payload: dict[str, Any]) -> dict[str, Any]:
    identities = player_identity_map(payload)
    ordered = _stats_profiles(payload)
    profiles = [profile for _, _, profile in ordered]
    final_score = _final_tape_score(payload)
    latest = profiles[-1] if profiles else None

    terminal_profiles = [
        profile for profile in profiles if _profile_is_terminal(profile, final_score)
    ]
    raw_profiles = [
        profile for profile in profiles if _profile_has_all_four_raw_both(profile)
    ]
    terminal_raw = [
        profile
        for profile in terminal_profiles
        if _profile_has_all_four_raw_both(profile)
    ]

    any_raw_slots: set[str] = set()
    terminal_raw_slots: set[str] = set()
    for profile in profiles:
        any_raw_slots.update(_profile_raw_slots(profile))
    for profile in terminal_profiles:
        terminal_raw_slots.update(_profile_raw_slots(profile))

    return {
        "stable_identity": bool(identities),
        "final_tape_score_present": final_score is not None,
        "stats_profile_count": len(profiles),
        "parseable_score_profile_count": sum(
            1 for profile in profiles if _profile_score(profile) is not None
        ),
        "latest_is_terminal": bool(
            latest and _profile_is_terminal(latest, final_score)
        ),
        "latest_has_all_four_raw_both": bool(
            latest and _profile_has_all_four_raw_both(latest)
        ),
        "any_all_four_raw_profile": bool(raw_profiles),
        "all_four_raw_profile_count": len(raw_profiles),
        "any_terminal_profile": bool(terminal_profiles),
        "terminal_profile_count": len(terminal_profiles),
        "any_terminal_all_four_raw_both": bool(terminal_raw),
        "terminal_all_four_raw_profile_count": len(terminal_raw),
        "latest_terminal_all_four_raw_both": bool(
            latest
            and _profile_is_terminal(latest, final_score)
            and _profile_has_all_four_raw_both(latest)
        ),
        "any_raw_slots": sorted(any_raw_slots),
        "terminal_raw_slots": sorted(terminal_raw_slots),
        "score_gap_kind": _score_gap_kind(profiles, final_score),
    }


def audit_payloads(payloads: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    profile_count_histogram = Counter()
    terminal_count_histogram = Counter()
    score_gap_kinds = Counter()
    raw_slot_any_profile = Counter()
    raw_slot_terminal_profile = Counter()

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        counts["matches_seen"] += 1
        item = inspect_snapshot_depth(payload)
        stable = item["stable_identity"] is True
        counts["stable_identity_matches"] += int(stable)
        counts["matches_without_stable_identity"] += int(not stable)
        if not stable:
            continue

        has_stats = int(item["stats_profile_count"]) > 0
        has_raw_anywhere = item["any_all_four_raw_profile"] is True
        has_terminal = item["any_terminal_profile"] is True
        has_terminal_raw = item["any_terminal_all_four_raw_both"] is True

        counts["matches_without_stats_profiles"] += int(not has_stats)
        counts["matches_with_stats_profiles"] += int(has_stats)
        counts["matches_with_no_final_tape_score"] += int(
            item["final_tape_score_present"] is not True
        )
        counts["matches_with_stats_but_no_parseable_score"] += int(
            has_stats and int(item["parseable_score_profile_count"]) == 0
        )
        counts["latest_terminal_matches"] += int(item["latest_is_terminal"])
        counts["latest_all_four_raw_matches"] += int(
            item["latest_has_all_four_raw_both"]
        )
        counts["latest_terminal_all_four_raw_matches"] += int(
            item["latest_terminal_all_four_raw_both"]
        )
        counts["matches_with_any_all_four_raw_profile"] += int(has_raw_anywhere)
        counts["matches_with_stats_but_no_any_all_four_raw"] += int(
            has_stats and not has_raw_anywhere
        )
        counts["matches_with_any_terminal_profile"] += int(has_terminal)
        counts["terminal_profile_missing_all_four_raw_matches"] += int(
            has_terminal and not has_terminal_raw
        )
        counts["matches_with_any_terminal_all_four_raw"] += int(has_terminal_raw)
        counts["raw_all_four_outside_terminal_proof_matches"] += int(
            has_raw_anywhere and not has_terminal_raw
        )
        counts["recoverable_if_latest_rule_is_only_blocker"] += int(
            has_terminal_raw
            and not item["latest_terminal_all_four_raw_both"]
        )

        profile_count_histogram[
            str(min(int(item["stats_profile_count"]), 20))
        ] += 1
        terminal_count_histogram[
            str(min(int(item["terminal_profile_count"]), 20))
        ] += 1
        score_gap_kinds[str(item["score_gap_kind"])] += 1

        for slot in item["any_raw_slots"]:
            raw_slot_any_profile[str(slot)] += 1
        for slot in item["terminal_raw_slots"]:
            raw_slot_terminal_profile[str(slot)] += 1

    stable = int(counts["stable_identity_matches"])
    stats_matches = int(counts["matches_with_stats_profiles"])
    any_raw = int(counts["matches_with_any_all_four_raw_profile"])
    latest_terminal_raw = int(counts["latest_terminal_all_four_raw_matches"])
    any_terminal_raw = int(counts["matches_with_any_terminal_all_four_raw"])
    selector_only = int(counts["recoverable_if_latest_rule_is_only_blocker"])
    raw_outside_terminal = int(
        counts["raw_all_four_outside_terminal_proof_matches"]
    )

    funnel_gaps = {
        "no_stats_profile": int(counts["matches_without_stats_profiles"]),
        "stats_profiles_but_no_all_four_raw_snapshot": int(
            counts["matches_with_stats_but_no_any_all_four_raw"]
        ),
        "all_four_raw_present_without_terminal_proof": raw_outside_terminal,
        "terminal_all_four_raw": any_terminal_raw,
    }
    candidate_gaps = {
        key: value
        for key, value in funnel_gaps.items()
        if key != "terminal_all_four_raw"
    }
    dominant_gap = (
        max(candidate_gaps, key=candidate_gaps.get)
        if candidate_gaps
        else None
    )

    def rate(value: int, denominator: int) -> float:
        return round(value / denominator, 6) if denominator else 0.0

    raw_slot_coverage = {
        slot: {
            "matches_with_raw_in_any_stats_profile": int(
                raw_slot_any_profile[slot]
            ),
            "rate_of_stats_profile_matches": rate(
                int(raw_slot_any_profile[slot]),
                stats_matches,
            ),
            "matches_with_raw_in_terminal_profile": int(
                raw_slot_terminal_profile[slot]
            ),
            "rate_of_stats_profile_matches_terminal": rate(
                int(raw_slot_terminal_profile[slot]),
                stats_matches,
            ),
        }
        for slot in RAW_SLOTS
    }

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
            "nonterminal_raw_evidence_used_for_production": False,
            "raw_outside_terminal_is_diagnostic_only": True,
            "training_join_enabled": False,
            "scorer_activation_enabled": False,
            "runtime_activation_enabled": False,
        },
        "counts": dict(counts),
        "depth_funnel": {
            "stable_identity_matches": stable,
            **funnel_gaps,
            "funnel_accounting_matches": sum(funnel_gaps.values()),
            "funnel_accounts_for_all_stable_matches": (
                sum(funnel_gaps.values()) == stable
            ),
            "dominant_observed_gap": dominant_gap,
            "note": (
                "The three gap buckets are observational. Raw evidence outside "
                "terminal proof is not safe canonical history by itself."
            ),
        },
        "score_gap_kinds": dict(
            sorted(score_gap_kinds.items(), key=lambda item: item[0])
        ),
        "raw_slot_coverage": raw_slot_coverage,
        "profile_count_histogram_capped_20": dict(
            sorted(profile_count_histogram.items(), key=lambda kv: int(kv[0]))
        ),
        "terminal_profile_count_histogram_capped_20": dict(
            sorted(terminal_count_histogram.items(), key=lambda kv: int(kv[0]))
        ),
        "comparison": {
            "current_latest_terminal_all_four_raw_matches": latest_terminal_raw,
            "any_terminal_all_four_raw_matches": any_terminal_raw,
            "potentially_recoverable_matches": selector_only,
            "recovery_multiplier": (
                round(any_terminal_raw / latest_terminal_raw, 6)
                if latest_terminal_raw
                else None
            ),
            "any_profile_all_four_raw_matches": any_raw,
            "raw_all_four_outside_terminal_proof_matches": raw_outside_terminal,
            "terminal_proof_capture_rate_of_any_raw_all_four": rate(
                any_terminal_raw,
                any_raw,
            ),
            "diagnostic_raw_depth_multiplier_vs_current_terminal": (
                round(any_raw / latest_terminal_raw, 6)
                if latest_terminal_raw
                else None
            ),
            "safe_selection_change_proven": False,
            "safe_terminal_relaxation_proven": False,
            "note": (
                "Coverage evidence only. Neither selector relaxation nor use of "
                "nonterminal raw snapshots is authorized by this audit."
            ),
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
    OUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    comparison = report["comparison"]
    funnel = report["depth_funnel"]
    print(
        "Service-split depth audit: "
        f"terminal_latest={comparison['current_latest_terminal_all_four_raw_matches']} "
        f"terminal_any={comparison['any_terminal_all_four_raw_matches']} "
        f"raw_any={comparison['any_profile_all_four_raw_matches']} "
        f"raw_without_terminal={comparison['raw_all_four_outside_terminal_proof_matches']} "
        f"dominant_gap={funnel['dominant_observed_gap']}"
    )


if __name__ == "__main__":
    main()
