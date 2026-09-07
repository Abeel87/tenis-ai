from __future__ import annotations

"""Audit PBP-native first/second serve-return split readiness for Player DNA.

This is a SHADOW source/readiness audit. It deliberately avoids the historical
CSV player-ID namespace, which #230 proved is incompatible with the Live Tennis
PBP provider IDs. The audit looks only at restored PBP payloads where
match.players.p1/p2 provide the same stable IDs already used by Player DNA.

No profile is built and no scorer/runtime path consumes these fields.
"""

import gzip
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from backend.player_identity import player_identity_map
except ModuleNotFoundError:  # direct execution compatibility
    from player_identity import player_identity_map

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT = ROOT / "frontend" / "data" / "player_dna_pbp_service_split_readiness.json"

VERSION = "player-dna-pbp-service-split-readiness-v1"
MODE = "SHADOW_PBP_SERVICE_SPLIT_READINESS_AUDIT_ONLY"
GATE = "AUDIT_ONLY_NO_PROFILE_BUILD"

SPLIT_FIELDS = (
    "first_serve_win_rate",
    "second_serve_win_rate",
    "first_return_win_rate",
    "second_return_win_rate",
)

DERIVED_KEYS = {
    "p1": {
        "first_serve_win_rate": "p1_first_serve_win_pct",
        "second_serve_win_rate": "p1_second_serve_win_pct",
        "first_return_win_rate": "p1_first_return_win_pct",
        "second_return_win_rate": "p1_second_return_win_pct",
    },
    "p2": {
        "first_serve_win_rate": "p2_first_serve_win_pct",
        "second_serve_win_rate": "p2_second_serve_win_pct",
        "first_return_win_rate": "p2_first_return_win_pct",
        "second_return_win_rate": "p2_second_return_win_pct",
    },
}

RAW_KEYS = {
    "first_serve_win_rate": "firstServePointsAccuracy",
    "second_serve_win_rate": "secondServePointsAccuracy",
    "first_return_win_rate": "firstReturnPoints",
    "second_return_win_rate": "secondReturnPoints",
}


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _rate(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        out = float(value)
        if math.isfinite(out) and 0.0 <= out <= 1.0:
            return out
        return None
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None

    # Prefer the observed numerator/denominator over a rounded displayed percent.
    if "/" in raw:
        left, right = raw.split("/", 1)
        try:
            numerator = float(left.strip())
            denominator_text = right.split(" ", 1)[0].split("(", 1)[0].strip()
            denominator = float(denominator_text)
        except (TypeError, ValueError):
            return None
        if denominator <= 0 or numerator < 0 or numerator > denominator:
            return None
        return numerator / denominator

    try:
        number = float(raw.rstrip("%"))
    except ValueError:
        return None
    if raw.endswith("%"):
        number /= 100.0
    return number if math.isfinite(number) and 0.0 <= number <= 1.0 else None


def _ratio_counts(value: Any) -> tuple[int, int] | None:
    """Parse an observed raw numerator/denominator pair as exact counts."""
    if not isinstance(value, str) or "/" not in value:
        return None
    left, right = value.strip().split("/", 1)
    try:
        numerator = float(left.strip())
        denominator_text = right.split(" ", 1)[0].split("(", 1)[0].strip()
        denominator = float(denominator_text)
    except (TypeError, ValueError):
        return None
    if (
        not math.isfinite(numerator)
        or not math.isfinite(denominator)
        or denominator <= 0
        or numerator < 0
        or numerator > denominator
        or abs(numerator - round(numerator)) > 1e-9
        or abs(denominator - round(denominator)) > 1e-9
    ):
        return None
    return int(round(numerator)), int(round(denominator))


def _score_core(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        return None
    sets = value.get("sets")
    games = value.get("games")
    if not isinstance(sets, list) or not isinstance(games, list):
        return None
    return json.dumps(sets, sort_keys=True), json.dumps(games, sort_keys=True)


def _final_tape_score(payload: dict[str, Any]) -> tuple[str, str] | None:
    rows = payload.get("tape")
    if not isinstance(rows, list):
        return None
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        score = _score_core(row)
        if score is not None:
            return score
    return None


def _latest_stats_profile(payload: dict[str, Any]) -> dict[str, Any] | None:
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        return None

    candidates = []
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict):
            continue
        state = profile.get("input_state")
        stats = state.get("stats") if isinstance(state, dict) else None
        if not isinstance(stats, dict):
            continue
        created = _parse_utc(profile.get("created_at"))
        candidates.append((created, index, profile))

    if not candidates:
        return None

    # Timestamp wins; stable source order is the fallback when timestamps are absent.
    candidates.sort(
        key=lambda item: (
            item[0] is not None,
            item[0] or datetime.min.replace(tzinfo=timezone.utc),
            item[1],
        )
    )
    return candidates[-1][2]


def _split_value(
    stats: dict[str, Any],
    side: str,
    field: str,
) -> tuple[float | None, str | None, bool | None]:
    derived = stats.get("derived") if isinstance(stats.get("derived"), dict) else {}
    raw_side = stats.get(side) if isinstance(stats.get(side), dict) else {}

    derived_value = _rate(derived.get(DERIVED_KEYS[side][field]))
    raw_value = _rate(raw_side.get(RAW_KEYS[field]))

    agreement = None
    if derived_value is not None and raw_value is not None:
        agreement = abs(derived_value - raw_value) <= 0.02

    if raw_value is not None:
        return raw_value, "raw_ratio", agreement
    if derived_value is not None:
        return derived_value, "derived_rate", agreement
    return None, None, agreement


def terminal_raw_service_split_match(
    payload: dict[str, Any],
    match_id: Any = None,
) -> dict[str, Any] | None:
    """Return leakage-safe exact service-split counts for one completed PBP match.

    Only raw numerator/denominator fields from a terminal stats snapshot are
    allowed. Rounded derived rates are intentionally excluded from canonical
    count aggregation.
    """
    identities = player_identity_map(payload)
    if not identities:
        return None

    profile = _latest_stats_profile(payload)
    if profile is None:
        return None
    state = profile.get("input_state") if isinstance(profile.get("input_state"), dict) else {}
    stats = state.get("stats") if isinstance(state.get("stats"), dict) else {}
    final_score = _final_tape_score(payload)
    snapshot_score = _score_core(state.get("score"))
    if final_score is None or snapshot_score is None or final_score != snapshot_score:
        return None

    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    scheduled = _parse_utc(match.get("scheduled_time"))
    if scheduled is None:
        return None
    surface = str(match.get("surface") or "unknown").strip().casefold() or "unknown"

    contributions: dict[int, dict[str, int]] = {}
    for side_no, side in ((1, "p1"), (2, "p2")):
        identity = identities.get(side_no) or {}
        player_id = identity.get("id")
        if isinstance(player_id, bool) or not isinstance(player_id, int):
            return None
        raw_side = stats.get(side) if isinstance(stats.get(side), dict) else {}
        contribution: dict[str, int] = {}
        for field in SPLIT_FIELDS:
            counts = _ratio_counts(raw_side.get(RAW_KEYS[field]))
            if counts is None:
                continue
            wins, points = counts
            prefix = field.removesuffix("_win_rate")
            contribution[f"{prefix}_matches"] = 1
            contribution[f"{prefix}_wins"] = wins
            contribution[f"{prefix}_points"] = points
        contributions[player_id] = contribution

    if not any(contributions.values()):
        return None

    resolved_match_id = match_id if match_id is not None else match.get("id")
    return {
        "match_id": str(resolved_match_id or "").strip(),
        "scheduled": scheduled,
        "surface": surface,
        "p1": int(identities[1]["id"]),
        "p2": int(identities[2]["id"]),
        "contrib": contributions,
        "raw_ratios_only": True,
        "terminal_stats_snapshot": True,
        "stable_pbp_provider_ids": True,
    }


def inspect_payload(payload: dict[str, Any]) -> dict[str, Any]:
    identities = player_identity_map(payload)
    if not identities:
        return {"stable_identity": False}

    profile = _latest_stats_profile(payload)
    if profile is None:
        return {"stable_identity": True, "stats_profile": False}

    state = profile.get("input_state") if isinstance(profile.get("input_state"), dict) else {}
    stats = state.get("stats") if isinstance(state.get("stats"), dict) else {}
    final_score = _final_tape_score(payload)
    snapshot_score = _score_core(state.get("score"))
    terminal_score_match = bool(
        final_score is not None
        and snapshot_score is not None
        and final_score == snapshot_score
    )

    sides: dict[str, Any] = {}
    all_four_both = True
    agreement_checks = []
    source_counts = Counter()
    for side in ("p1", "p2"):
        values = {}
        for field in SPLIT_FIELDS:
            value, source, agrees = _split_value(stats, side, field)
            values[field] = value
            values[f"{field}_source"] = source
            source_counts[str(source or "missing")] += 1
            if agrees is not None:
                agreement_checks.append(bool(agrees))
            if value is None:
                all_four_both = False
        sides[side] = values

    return {
        "stable_identity": True,
        "stats_profile": True,
        "profile_created_at": profile.get("created_at"),
        "terminal_score_match": terminal_score_match,
        "all_four_splits_both_players": all_four_both,
        "split_values": sides,
        "raw_vs_derived_checks": len(agreement_checks),
        "raw_vs_derived_agreements": sum(1 for ok in agreement_checks if ok),
        "raw_vs_derived_all_agree": bool(agreement_checks and all(agreement_checks)),
        "value_sources": dict(source_counts),
    }


def audit_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    field_ready = Counter()
    source_counts = Counter()

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        counts["matches_seen"] += 1
        item = inspect_payload(payload)

        stable = item.get("stable_identity") is True
        counts["stable_identity_matches"] += int(stable)
        if not stable:
            continue

        has_profile = item.get("stats_profile") is True
        counts["matches_with_stats_profile"] += int(has_profile)
        if not has_profile:
            continue

        terminal = item.get("terminal_score_match") is True
        all_four = item.get("all_four_splits_both_players") is True
        counts["matches_with_terminal_stats_snapshot"] += int(terminal)
        counts["matches_with_all_four_splits_both_players"] += int(all_four)
        counts["terminal_matches_with_all_four_splits"] += int(terminal and all_four)

        counts["raw_vs_derived_checks"] += int(item.get("raw_vs_derived_checks") or 0)
        counts["raw_vs_derived_agreements"] += int(item.get("raw_vs_derived_agreements") or 0)

        for source, number in (item.get("value_sources") or {}).items():
            source_counts[str(source)] += int(number)

        for side in ("p1", "p2"):
            values = (item.get("split_values") or {}).get(side) or {}
            for field in SPLIT_FIELDS:
                field_ready[f"{side}_{field}"] += int(values.get(field) is not None)

    total = int(counts["matches_seen"])
    stable = int(counts["stable_identity_matches"])
    stats_profiles = int(counts["matches_with_stats_profile"])
    all_four = int(counts["matches_with_all_four_splits_both_players"])
    terminal_all_four = int(counts["terminal_matches_with_all_four_splits"])
    checks = int(counts["raw_vs_derived_checks"])
    agreements = int(counts["raw_vs_derived_agreements"])

    def rate(value: int, denominator: int) -> float:
        return round(value / denominator, 6) if denominator else 0.0

    # Coverage gate only: it does not say the fields improve prediction.
    material_terminal_sample = terminal_all_four >= 100
    agreement_rate = rate(agreements, checks)
    semantic_consistency = checks >= 100 and agreement_rate >= 0.97
    source_ready = bool(material_terminal_sample and semantic_consistency)

    return {
        "version": VERSION,
        "mode": MODE,
        "gate": GATE,
        "source": "restored Live Tennis API PBP payloads only",
        "matches_seen": total,
        "stable_identity_matches": stable,
        "stable_identity_rate": rate(stable, total),
        "matches_with_stats_profile": stats_profiles,
        "stats_profile_rate_of_stable": rate(stats_profiles, stable),
        "matches_with_all_four_splits_both_players": all_four,
        "all_four_rate_of_stats_profiles": rate(all_four, stats_profiles),
        "matches_with_terminal_stats_snapshot": int(counts["matches_with_terminal_stats_snapshot"]),
        "terminal_matches_with_all_four_splits": terminal_all_four,
        "terminal_all_four_rate_of_stable": rate(terminal_all_four, stable),
        "field_coverage": {
            key: {
                "matches": int(value),
                "rate_of_stats_profiles": rate(int(value), stats_profiles),
            }
            for key, value in sorted(field_ready.items())
        },
        "value_sources": dict(source_counts),
        "raw_vs_derived_consistency": {
            "checks": checks,
            "agreements_within_2pp": agreements,
            "agreement_rate": agreement_rate,
            "minimum_checks_for_gate": 100,
            "minimum_agreement_rate_for_gate": 0.97,
            "semantic_consistency_gate_passed": semantic_consistency,
        },
        "readiness": {
            "stable_pbp_provider_ids_same_namespace_as_player_dna": True,
            "cross_source_id_join_required": False,
            "material_terminal_sample": material_terminal_sample,
            "source_ready_for_canonical_profile_design": source_ready,
            "predictive_signal_proven": False,
        },
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "profile_build_enabled": False,
        "training_join_enabled": False,
        "matchup_feature_activation_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "contract": {
            "pbp_native_provider_ids_only": True,
            "historical_csv_id_namespace_not_used": True,
            "name_or_fuzzy_join_forbidden": True,
            "latest_stats_profile_selected_without_future_target_context": True,
            "terminal_snapshot_requires_same_sets_and_games_as_final_tape": True,
            "raw_ratio_preferred_over_rounded_derived_rate": True,
            "coverage_is_not_predictive_signal": True,
            "profile_build_requires_separate_gate": True,
            "chronological_backtest_required_after_profile_gate": True,
        },
        "next_gate": (
            "If terminal PBP-native split coverage and raw/derived semantic consistency "
            "pass, add first/second serve and return rates to the canonical strict-as-of "
            "Player DNA profile store using only stable PBP provider IDs. Each target "
            "snapshot must use only completed source matches scheduled strictly before it."
        ),
    }


def build(cache_dir: Path = CACHE) -> dict[str, Any]:
    payloads = []
    if cache_dir.exists():
        for path in sorted(cache_dir.glob("*.json.gz")):
            payload = _read(path)
            if payload is not None:
                payloads.append(payload)

    report = audit_payloads(payloads)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
