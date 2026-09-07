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

VERSION = "player-dna-service-split-depth-audit-v3"
MODE = "SHADOW_DIAGNOSTIC_ONLY"

RAW_SLOTS = tuple(
    f"{side}_{field}"
    for side in ("p1", "p2")
    for field in SPLIT_FIELDS
)


def _profile_capture_shape(payload: dict[str, Any]) -> dict[str, int]:
    entries = payload.get("profiles")
    if not isinstance(entries, list):
        entries = []
    dict_profiles = [item for item in entries if isinstance(item, dict)]
    input_states = [
        item.get("input_state")
        for item in dict_profiles
        if isinstance(item.get("input_state"), dict)
    ]
    stats_dicts = [
        state.get("stats")
        for state in input_states
        if isinstance(state.get("stats"), dict)
    ]
    return {
        "profile_entry_count": len(entries),
        "profile_dict_count": len(dict_profiles),
        "input_state_profile_count": len(input_states),
        "stats_dict_profile_count": len(stats_dicts),
    }


def _no_stats_capture_reason(shape: dict[str, int]) -> str | None:
    if int(shape.get("stats_dict_profile_count") or 0) > 0:
        return None
    if int(shape.get("profile_entry_count") or 0) == 0:
        return "no_profile_entries"
    if int(shape.get("profile_dict_count") or 0) == 0:
        return "profile_entries_not_dicts"
    if int(shape.get("input_state_profile_count") or 0) == 0:
        return "profiles_without_input_state"
    return "input_state_without_stats_dict"


def _raw_slots_from_stats_like(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    present: set[str] = set()
    for side in ("p1", "p2"):
        raw_side = value.get(side) if isinstance(value.get(side), dict) else {}
        for field in SPLIT_FIELDS:
            if _ratio_counts(raw_side.get(RAW_KEYS[field])) is not None:
                present.add(f"{side}_{field}")
    return present


def _scan_alternate_raw_containers(payload: dict[str, Any]) -> dict[str, int]:
    """Find cached stats-like raw containers outside the canonical capture path.

    This is diagnostic only. A hit proves bytes exist somewhere in the cached
    payload, not that their semantics/timing are safe for Player DNA history.
    """
    stack: list[Any] = [payload]
    max_slots = 0
    containers_with_raw = 0
    containers_with_all_slots = 0
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            slots = _raw_slots_from_stats_like(value)
            if slots:
                containers_with_raw += 1
                max_slots = max(max_slots, len(slots))
                containers_with_all_slots += int(len(slots) == len(RAW_SLOTS))
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return {
        "max_raw_slots_in_one_container": max_slots,
        "containers_with_any_raw_slots": containers_with_raw,
        "containers_with_all_raw_slots": containers_with_all_slots,
    }


def _match_context_buckets(payload: dict[str, Any]) -> tuple[str, str]:
    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    surface = str(match.get("surface") or "unknown").strip().casefold() or "unknown"
    scheduled = _parse_utc(match.get("scheduled_time"))
    month = scheduled.strftime("%Y-%m") if scheduled is not None else "unknown"
    return surface, month


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
    capture_shape = _profile_capture_shape(payload)
    ordered = _stats_profiles(payload)
    profiles = [profile for _, _, profile in ordered]
    final_score = _final_tape_score(payload)
    latest = profiles[-1] if profiles else None
    no_stats_reason = _no_stats_capture_reason(capture_shape)
    alternate_raw = (
        _scan_alternate_raw_containers(payload)
        if not profiles
        else {
            "max_raw_slots_in_one_container": 0,
            "containers_with_any_raw_slots": 0,
            "containers_with_all_raw_slots": 0,
        }
    )
    surface_bucket, month_bucket = _match_context_buckets(payload)

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
        **capture_shape,
        "stats_profile_count": len(profiles),
        "no_stats_capture_reason": no_stats_reason,
        "alternate_raw_evidence": alternate_raw,
        "match_surface_bucket": surface_bucket,
        "match_month_bucket": month_bucket,
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
    no_stats_capture_reasons = Counter()
    alternate_raw_evidence_kinds = Counter()
    alternate_raw_max_slot_histogram = Counter()
    stats_capture_by_surface: dict[str, Counter] = {}
    stats_capture_by_month: dict[str, Counter] = {}

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

        for bucket_map, bucket_name in (
            (stats_capture_by_surface, str(item["match_surface_bucket"])),
            (stats_capture_by_month, str(item["match_month_bucket"])),
        ):
            bucket = bucket_map.setdefault(bucket_name, Counter())
            bucket["stable_matches"] += 1
            bucket["with_stats_profiles"] += int(has_stats)
            bucket["without_stats_profiles"] += int(not has_stats)

        if not has_stats:
            reason = str(item["no_stats_capture_reason"] or "unknown")
            no_stats_capture_reasons[reason] += 1
            alternate = item["alternate_raw_evidence"] or {}
            max_slots = int(alternate.get("max_raw_slots_in_one_container") or 0)
            alternate_raw_max_slot_histogram[str(max_slots)] += 1
            if max_slots == len(RAW_SLOTS):
                alternate_raw_evidence_kinds["all_four_raw_cached_elsewhere"] += 1
            elif max_slots > 0:
                alternate_raw_evidence_kinds["partial_raw_cached_elsewhere"] += 1
            else:
                alternate_raw_evidence_kinds["no_raw_stats_like_container_found"] += 1

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

    missing_stats = int(counts["matches_without_stats_profiles"])
    no_stats_reason_total = sum(no_stats_capture_reasons.values())
    alternate_raw_total = sum(alternate_raw_evidence_kinds.values())

    def capture_breakdown(source: dict[str, Counter]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for bucket_name, bucket in sorted(source.items()):
            stable_bucket = int(bucket["stable_matches"])
            with_stats = int(bucket["with_stats_profiles"])
            without_stats = int(bucket["without_stats_profiles"])
            out[bucket_name] = {
                "stable_matches": stable_bucket,
                "with_stats_profiles": with_stats,
                "without_stats_profiles": without_stats,
                "stats_profile_rate": rate(with_stats, stable_bucket),
            }
        return out

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
            "alternate_raw_container_scan_diagnostic_only": True,
            "alternate_raw_container_authorized_for_history": False,
            "stats_capture_gap_diagnostic_only": True,
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
        "stats_capture_gap": {
            "matches_without_stats_profiles": missing_stats,
            "no_stats_capture_reasons": dict(
                sorted(no_stats_capture_reasons.items(), key=lambda item: item[0])
            ),
            "reason_accounting_matches": no_stats_reason_total,
            "reasons_account_for_all_missing_stats": (
                no_stats_reason_total == missing_stats
            ),
            "alternate_raw_evidence": dict(
                sorted(alternate_raw_evidence_kinds.items(), key=lambda item: item[0])
            ),
            "alternate_raw_accounting_matches": alternate_raw_total,
            "alternate_raw_accounts_for_all_missing_stats": (
                alternate_raw_total == missing_stats
            ),
            "alternate_raw_max_slots_histogram": dict(
                sorted(
                    alternate_raw_max_slot_histogram.items(),
                    key=lambda item: int(item[0]),
                )
            ),
            "by_surface": capture_breakdown(stats_capture_by_surface),
            "by_scheduled_month": capture_breakdown(stats_capture_by_month),
            "note": (
                "Alternate raw containers are an extraction/source diagnostic only. "
                "They are not terminally proven and cannot enter canonical history "
                "without a separate semantics/timing gate."
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
        f"no_stats={report['stats_capture_gap']['matches_without_stats_profiles']} "
        f"alt_raw_all4={(report['stats_capture_gap']['alternate_raw_evidence'] or {}).get('all_four_raw_cached_elsewhere', 0)} "
        f"dominant_gap={funnel['dominant_observed_gap']}"
    )


if __name__ == "__main__":
    main()
