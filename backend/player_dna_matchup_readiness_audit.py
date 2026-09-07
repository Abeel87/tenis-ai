from __future__ import annotations

"""Phase-3 Matchup Engine readiness audit for canonical Player DNA.

This module is deliberately audit-only. It consumes the existing canonical
strict-as-of Player DNA snapshots and measures whether both sides of concrete
pairwise matchup interactions are available before each target match.

It does not create matchup scores, fit a model, change the point scorer,
simulator, PROD, Symfonia 2.0, or Superbet PLAYABLE.
"""

import gzip
import json
import math
from collections import Counter
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_shadow_profiles import OUT_JSONL as PROFILES
    from backend.player_dna_shadow_profiles import THRESHOLDS
except ModuleNotFoundError:  # direct execution compatibility
    from player_dna_shadow_profiles import OUT_JSONL as PROFILES
    from player_dna_shadow_profiles import THRESHOLDS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "data" / "player_dna_matchup_readiness_audit.json"

VERSION = "player-dna-matchup-readiness-audit-v1"
MODE = "SHADOW_MATCHUP_READINESS_AUDIT_ONLY"
GATE = "AUDIT_ONLY_NO_MATCHUP_FEATURES"

CONTEXTS = {
    "overall": "overall_prior",
    "same_surface": "same_surface_prior",
}

# Each pair is evaluated in both directions: player A's left field against
# player B's right field, then B against A.
INTERACTIONS = {
    "serve_vs_return": ("serve_win_rate", "return_win_rate"),
    "first_serve_vs_first_return": ("first_serve_win_rate", "first_return_win_rate"),
    "second_serve_vs_second_return": ("second_serve_win_rate", "second_return_win_rate"),
    "hold_vs_break": ("hold_rate", "break_rate"),
    "bp_save_vs_conversion": ("bp_save_rate", "bp_conversion_rate"),
    "deuce_serve_vs_return": ("deuce_serve_win_rate", "deuce_return_win_rate"),
    "thirty_all_serve_vs_return": (
        "thirty_all_serve_win_rate",
        "thirty_all_return_win_rate",
    ),
    "early_game_1_hold_vs_break": (
        "early_service_game_1_hold_rate",
        "early_return_game_1_break_rate",
    ),
    "early_game_2_hold_vs_break": (
        "early_service_game_2_hold_rate",
        "early_return_game_2_break_rate",
    ),
    "early_game_3_hold_vs_break": (
        "early_service_game_3_hold_rate",
        "early_return_game_3_break_rate",
    ),
    "tiebreak_vs_tiebreak": ("tiebreak_win_rate", "tiebreak_win_rate"),
}

# Service-split rates have their own raw prior-match support counts. They must
# not borrow generic Player DNA match support, otherwise one split observation
# could masquerade as a 3/5-match service-split profile.
FIELD_SUPPORT_MATCH_KEYS = {
    "first_serve_win_rate": "first_serve_matches",
    "second_serve_win_rate": "second_serve_matches",
    "first_return_win_rate": "first_return_matches",
    "second_return_win_rate": "second_return_matches",
}

# Master-plan matchup families that are not yet represented by a reliable
# canonical pre-match Player DNA field pair. This is an explicit readiness gap,
# not a claim that the raw source can never support them.
NOT_CANONICALLY_AVAILABLE = {
    "ace_vs_contact_return": {
        "reason": "no canonical ace/contact profile",
        "requires_separate_source_readiness_audit": True,
    },
    "double_fault_vs_return_pressure": {
        "reason": "no canonical double-fault/return-pressure profile",
        "requires_separate_source_readiness_audit": True,
    },
    "after_break_response": {
        "reason": "no canonical pre-match after-break response profile",
        "requires_separate_source_readiness_audit": True,
    },
    "first_set_vs_first_set": {
        "reason": "no canonical first-set outcome profile in Player DNA snapshots",
        "requires_separate_source_readiness_audit": True,
    },
    "stamina_long_match_bo5": {
        "reason": "no canonical stamina/long-match profile",
        "requires_separate_source_readiness_audit": True,
    },
}


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


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _finite_rate(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        return None
    return number


def iter_profile_rows(path: Path = PROFILES) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _valid_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter]:
    counters = Counter()
    valid: list[dict[str, Any]] = []

    for raw in rows:
        counters["rows_seen"] += 1
        if not isinstance(raw, dict):
            counters["non_dict"] += 1
            continue
        if raw.get("mode") != "SHADOW_AS_OF_PROFILE":
            counters["wrong_mode"] += 1
            continue
        if raw.get("strict_as_of") is not True:
            counters["non_strict_as_of"] += 1
            continue
        if raw.get("same_time_matches_count_as_prior") is not False:
            counters["same_time_policy_invalid"] += 1
            continue

        match_id = str(raw.get("target_match_id") or "").strip()
        scheduled = _parse_utc(raw.get("target_scheduled_time"))
        player_id = _positive_int(raw.get("player_id"))
        opponent_id = _positive_int(raw.get("opponent_id"))
        if (
            not match_id
            or scheduled is None
            or player_id is None
            or opponent_id is None
            or player_id == opponent_id
        ):
            counters["invalid_identity_or_time"] += 1
            continue

        row = dict(raw)
        row["_match_id"] = match_id
        row["_scheduled"] = scheduled
        row["_player_id"] = player_id
        row["_opponent_id"] = opponent_id
        row["_surface"] = str(raw.get("target_surface") or "unknown").strip().lower()
        valid.append(row)
        counters["valid_rows"] += 1

    valid.sort(
        key=lambda row: (
            row["_scheduled"],
            row["_match_id"],
            row["_player_id"],
        )
    )
    return valid, counters


def _paired_matches(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Counter]:
    counters = Counter()
    matches: list[dict[str, Any]] = []

    for (scheduled, match_id), group_iter in groupby(
        rows,
        key=lambda row: (row["_scheduled"], row["_match_id"]),
    ):
        group = list(group_iter)
        if len(group) != 2:
            counters["non_pair_groups"] += 1
            continue

        first, second = group
        if (
            first["_player_id"] != second["_opponent_id"]
            or second["_player_id"] != first["_opponent_id"]
        ):
            counters["non_reciprocal_pairs"] += 1
            continue
        if first["_surface"] != second["_surface"]:
            counters["surface_conflicts"] += 1
            continue

        by_player = {
            first["_player_id"]: first,
            second["_player_id"]: second,
        }
        players = tuple(sorted(by_player))
        matches.append(
            {
                "scheduled": scheduled,
                "match_id": match_id,
                "surface": first["_surface"],
                "players": players,
                "rows": by_player,
            }
        )
        counters["paired_matches"] += 1

    return matches, counters


def _profile(row: dict[str, Any], context: str) -> dict[str, Any]:
    key = CONTEXTS[context]
    raw = row.get(key)
    return raw if isinstance(raw, dict) else {}


def _field_support_matches(profile: dict[str, Any], field: str) -> int:
    support_key = FIELD_SUPPORT_MATCH_KEYS.get(field)
    if support_key is None:
        support_key = "matches"
    try:
        value = int(profile.get(support_key) or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, value)


def _direction_ready(
    attacker: dict[str, Any],
    defender: dict[str, Any],
    context: str,
    left_field: str,
    right_field: str,
    threshold: int,
) -> bool:
    left = _profile(attacker, context)
    right = _profile(defender, context)
    return bool(
        _field_support_matches(left, left_field) >= threshold
        and _field_support_matches(right, right_field) >= threshold
        and _finite_rate(left.get(left_field)) is not None
        and _finite_rate(right.get(right_field)) is not None
    )


def audit_profile_snapshots(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    valid, source_counts = _valid_rows(rows)
    matches, pair_counts = _paired_matches(valid)

    directional_total = len(matches) * 2
    interaction_counts: dict[str, dict[str, Counter]] = {
        context: {
            name: Counter()
            for name in INTERACTIONS
        }
        for context in CONTEXTS
    }

    fully_ready_match_counts: dict[str, Counter] = {
        context: Counter() for context in CONTEXTS
    }

    for match in matches:
        p1, p2 = match["players"]
        directions = (
            (match["rows"][p1], match["rows"][p2]),
            (match["rows"][p2], match["rows"][p1]),
        )

        for context in CONTEXTS:
            for threshold in THRESHOLDS:
                match_all_ready = True
                for interaction_name, (left_field, right_field) in INTERACTIONS.items():
                    ready_directions = 0
                    for attacker, defender in directions:
                        if _direction_ready(
                            attacker,
                            defender,
                            context,
                            left_field,
                            right_field,
                            threshold,
                        ):
                            ready_directions += 1
                    interaction_counts[context][interaction_name][threshold] += (
                        ready_directions
                    )
                    if ready_directions != 2:
                        match_all_ready = False
                if match_all_ready:
                    fully_ready_match_counts[context][threshold] += 1

    coverage: dict[str, Any] = {}
    for context in CONTEXTS:
        coverage[context] = {}
        for interaction_name, fields in INTERACTIONS.items():
            by_threshold = {}
            for threshold in THRESHOLDS:
                ready = int(interaction_counts[context][interaction_name][threshold])
                by_threshold[str(threshold)] = {
                    "required_prior_matches_per_player": int(threshold),
                    "ready_directions": ready,
                    "directions": directional_total,
                    "rate": (
                        round(ready / directional_total, 6)
                        if directional_total
                        else 0.0
                    ),
                }
            coverage[context][interaction_name] = {
                "left_field": fields[0],
                "right_field": fields[1],
                "by_threshold": by_threshold,
            }

    full_match_coverage = {
        context: {
            str(threshold): {
                "matches_ready_for_all_current_interactions": int(
                    fully_ready_match_counts[context][threshold]
                ),
                "paired_matches": len(matches),
                "rate": (
                    round(
                        int(fully_ready_match_counts[context][threshold])
                        / len(matches),
                        6,
                    )
                    if matches
                    else 0.0
                ),
            }
            for threshold in THRESHOLDS
        }
        for context in CONTEXTS
    }

    return {
        "version": VERSION,
        "mode": MODE,
        "gate": GATE,
        "phase": "PHASE_3_MATCHUP_ENGINE_READINESS",
        "network_calls": 0,
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "training_join_enabled": False,
        "matchup_feature_activation_enabled": False,
        "canonical_profile_write_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "source_counts": dict(source_counts),
        "pair_counts": dict(pair_counts),
        "paired_matches": len(matches),
        "directional_matchups": directional_total,
        "contexts": list(CONTEXTS),
        "thresholds": list(THRESHOLDS),
        "canonical_interactions": {
            name: {
                "left_field": fields[0],
                "right_field": fields[1],
            }
            for name, fields in INTERACTIONS.items()
        },
        "coverage": coverage,
        "full_match_coverage": full_match_coverage,
        "not_canonically_available": NOT_CANONICALLY_AVAILABLE,
        "contract": {
            "canonical_strict_as_of_profiles_only": True,
            "same_timestamp_matches_never_count_as_prior": True,
            "stable_provider_player_ids_only": True,
            "reciprocal_target_match_pairs_only": True,
            "no_fuzzy_identity": True,
            "no_matchup_score_computed": True,
            "no_interaction_weight_tuned": True,
            "no_model_threshold_activated": True,
            "coverage_is_readiness_not_signal": True,
            "future_matchup_candidate_requires_chronological_walk_forward": True,
        },
        "next_gate": (
            "Choose only interactions with measured support, define a single "
            "predeclared matchup formulation, and compare it against the current "
            "lean-stateful reference in chronological walk-forward. Missing "
            "master-plan families require separate source-readiness evidence "
            "before they enter the canonical Player DNA profile."
        ),
    }


def build() -> dict[str, Any]:
    report = audit_profile_snapshots(iter_profile_rows() or ())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
