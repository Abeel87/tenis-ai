from __future__ import annotations

"""Audit exact PBP match-state readiness for comeback and BO5 stamina profiles.

This is a zero-network SHADOW readiness audit. It uses only stable Live Tennis
provider IDs and exact score-state transitions already present in restored PBP
payloads. It does not build Player DNA profiles or activate any model feature.

A match is eligible only when:
- stable p1/p2 provider IDs exist,
- scheduled_time is valid,
- latest stats snapshot score exactly matches the final tape score,
- the final set score is a legal completed BO3/BO5 score,
- the tape proves the complete set-winner sequence from 0:0 by atomic +1 set
  transitions with no jumps/regressions.

That proof is intentionally stricter than merely seeing a final score because
comeback and stamina semantics depend on set order.
"""

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from backend.player_dna_pbp_service_split_readiness import (
        _final_tape_score,
        _latest_stats_profile,
        _parse_utc,
        _score_core,
    )
    from backend.player_identity import player_identity_map
except ModuleNotFoundError:  # direct execution compatibility
    from player_dna_pbp_service_split_readiness import (
        _final_tape_score,
        _latest_stats_profile,
        _parse_utc,
        _score_core,
    )
    from player_identity import player_identity_map

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pbp_v7" / "matches"
OUT = ROOT / "frontend" / "data" / "player_dna_match_state_readiness.json"

VERSION = "player-dna-match-state-readiness-v1"
MODE = "SHADOW_MATCH_STATE_READINESS_AUDIT_ONLY"
GATE = "AUDIT_ONLY_NO_PROFILE_BUILD"
SUPPORT_THRESHOLDS = (1, 3, 5, 10)


def _read(path: Path) -> dict[str, Any] | None:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _sets(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    sets = value.get("sets")
    if (
        not isinstance(sets, list)
        or len(sets) != 2
        or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in sets)
    ):
        return None
    return int(sets[0]), int(sets[1])


def _legal_completed_match(final_sets: tuple[int, int]) -> tuple[int, int] | None:
    s1, s2 = final_sets
    if (s1 == 2 and 0 <= s2 <= 1) or (s2 == 2 and 0 <= s1 <= 1):
        return 3, 1 if s1 == 2 else 2
    if (s1 == 3 and 0 <= s2 <= 2) or (s2 == 3 and 0 <= s1 <= 2):
        return 5, 1 if s1 == 3 else 2
    return None


def _exact_set_winner_sequence(payload: dict[str, Any]) -> list[int] | None:
    tape = payload.get("tape")
    if not isinstance(tape, list):
        return None

    observed = []
    for row in tape:
        if not isinstance(row, dict):
            continue
        score = _sets(row)
        if score is None:
            continue
        if not observed or score != observed[-1]:
            observed.append(score)

    if not observed or observed[0] != (0, 0):
        return None

    previous = observed[0]
    winners: list[int] = []
    for current in observed[1:]:
        d1 = current[0] - previous[0]
        d2 = current[1] - previous[1]
        if (d1, d2) == (1, 0):
            winners.append(1)
        elif (d1, d2) == (0, 1):
            winners.append(2)
        elif (d1, d2) == (0, 0):
            pass
        else:
            return None
        previous = current

    if (winners.count(1), winners.count(2)) != previous:
        return None
    return winners


def inspect_payload(payload: dict[str, Any]) -> dict[str, Any]:
    identities = player_identity_map(payload)
    if not identities:
        return {"stable_identity": False}

    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    scheduled = _parse_utc(match.get("scheduled_time"))
    if scheduled is None:
        return {
            "stable_identity": True,
            "scheduled_time": False,
        }

    profile = _latest_stats_profile(payload)
    if profile is None:
        return {
            "stable_identity": True,
            "scheduled_time": True,
            "stats_profile": False,
        }

    state = profile.get("input_state") if isinstance(profile.get("input_state"), dict) else {}
    final_score = _final_tape_score(payload)
    snapshot_score = _score_core(state.get("score"))
    terminal = bool(
        final_score is not None
        and snapshot_score is not None
        and final_score == snapshot_score
    )
    if not terminal:
        return {
            "stable_identity": True,
            "scheduled_time": True,
            "stats_profile": True,
            "terminal_score_match": False,
        }

    tape = payload.get("tape")
    final_sets = None
    if isinstance(tape, list):
        for row in reversed(tape):
            if isinstance(row, dict):
                final_sets = _sets(row)
                if final_sets is not None:
                    break

    legal = _legal_completed_match(final_sets) if final_sets is not None else None
    if legal is None:
        return {
            "stable_identity": True,
            "scheduled_time": True,
            "stats_profile": True,
            "terminal_score_match": True,
            "legal_completed_match": False,
            "final_sets": list(final_sets) if final_sets is not None else None,
        }

    best_of, match_winner = legal
    sequence = _exact_set_winner_sequence(payload)
    exact_sequence = bool(
        sequence is not None
        and len(sequence) == sum(final_sets)
        and sequence.count(1) == final_sets[0]
        and sequence.count(2) == final_sets[1]
        and sequence[-1] == match_winner
    )

    p1_id = int(identities[1]["id"])
    p2_id = int(identities[2]["id"])
    first_set_winner = sequence[0] if exact_sequence and sequence else None
    first_set_loser = (
        2 if first_set_winner == 1
        else 1 if first_set_winner == 2
        else None
    )
    comeback = bool(
        exact_sequence
        and first_set_loser is not None
        and match_winner == first_set_loser
    )

    return {
        "stable_identity": True,
        "scheduled_time": True,
        "stats_profile": True,
        "terminal_score_match": True,
        "legal_completed_match": True,
        "exact_set_winner_sequence": exact_sequence,
        "match_id": str(match.get("id") or "").strip(),
        "scheduled": scheduled.isoformat(),
        "surface": str(match.get("surface") or "unknown").strip().casefold() or "unknown",
        "p1_id": p1_id,
        "p2_id": p2_id,
        "best_of": best_of,
        "final_sets": list(final_sets),
        "match_winner_side": match_winner,
        "set_winner_sequence": list(sequence) if exact_sequence and sequence else None,
        "first_set_winner_side": first_set_winner,
        "first_set_loser_side": first_set_loser,
        "comeback_after_losing_first_set": comeback if exact_sequence else None,
        "late_set_count": max(0, len(sequence) - 2) if exact_sequence and sequence else None,
        "late_set_winners": list(sequence[2:]) if exact_sequence and sequence else None,
    }


def _threshold_report(counter: Counter[int]) -> dict[str, dict[str, int]]:
    players = set(counter)
    return {
        str(threshold): {
            "players": sum(1 for pid in players if int(counter[pid]) >= threshold),
        }
        for threshold in SUPPORT_THRESHOLDS
    }


def audit_payloads(payloads: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    comeback_exposures: Counter[int] = Counter()
    comeback_wins: Counter[int] = Counter()
    bo5_matches: Counter[int] = Counter()
    bo5_late_sets: Counter[int] = Counter()
    bo5_late_set_wins: Counter[int] = Counter()

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        counts["matches_seen"] += 1
        item = inspect_payload(payload)

        stable = item.get("stable_identity") is True
        counts["stable_identity_matches"] += int(stable)
        if not stable:
            continue

        scheduled = item.get("scheduled_time") is True
        counts["matches_with_scheduled_time"] += int(scheduled)
        if not scheduled:
            continue

        stats_profile = item.get("stats_profile") is True
        counts["matches_with_stats_profile"] += int(stats_profile)
        if not stats_profile:
            continue

        terminal = item.get("terminal_score_match") is True
        counts["matches_with_terminal_score_proof"] += int(terminal)
        if not terminal:
            continue

        legal = item.get("legal_completed_match") is True
        counts["legal_completed_matches"] += int(legal)
        if not legal:
            continue

        exact_sequence = item.get("exact_set_winner_sequence") is True
        counts["matches_with_exact_set_sequence"] += int(exact_sequence)
        if not exact_sequence:
            continue

        pids = {
            1: int(item["p1_id"]),
            2: int(item["p2_id"]),
        }
        first_loser = int(item["first_set_loser_side"])
        match_winner = int(item["match_winner_side"])
        loser_pid = pids[first_loser]
        comeback_exposures[loser_pid] += 1
        comeback_wins[loser_pid] += int(match_winner == first_loser)
        counts["first_set_loss_player_exposures"] += 1
        counts["comeback_wins_after_first_set_loss"] += int(match_winner == first_loser)

        best_of = int(item["best_of"])
        counts[f"bo{best_of}_exact_matches"] += 1

        if best_of == 5:
            sequence = list(item["set_winner_sequence"])
            for pid in pids.values():
                bo5_matches[pid] += 1
            counts["bo5_player_match_exposures"] += 2

            for winner_side in sequence[2:]:
                winner_side = int(winner_side)
                loser_side = 2 if winner_side == 1 else 1
                bo5_late_sets[pids[winner_side]] += 1
                bo5_late_sets[pids[loser_side]] += 1
                bo5_late_set_wins[pids[winner_side]] += 1
                counts["bo5_late_set_player_exposures"] += 2
                counts["bo5_late_set_wins"] += 1

    exact_matches = int(counts["matches_with_exact_set_sequence"])
    legal_matches = int(counts["legal_completed_matches"])
    comeback_total = int(counts["first_set_loss_player_exposures"])
    comeback_wins_total = int(counts["comeback_wins_after_first_set_loss"])
    bo5_exact = int(counts["bo5_exact_matches"])

    def rate(value: int, denominator: int) -> float:
        return round(value / denominator, 6) if denominator else 0.0

    return {
        "version": VERSION,
        "mode": MODE,
        "gate": GATE,
        "source": "restored Live Tennis API PBP payloads only",
        "network_calls": 0,
        "matches_seen": int(counts["matches_seen"]),
        "stable_identity_matches": int(counts["stable_identity_matches"]),
        "matches_with_scheduled_time": int(counts["matches_with_scheduled_time"]),
        "matches_with_stats_profile": int(counts["matches_with_stats_profile"]),
        "matches_with_terminal_score_proof": int(counts["matches_with_terminal_score_proof"]),
        "legal_completed_matches": legal_matches,
        "matches_with_exact_set_sequence": exact_matches,
        "exact_set_sequence_rate_of_legal": rate(exact_matches, legal_matches),
        "format_coverage": {
            "bo3_exact_matches": int(counts["bo3_exact_matches"]),
            "bo5_exact_matches": bo5_exact,
        },
        "comeback_readiness": {
            "first_set_loss_player_exposures": comeback_total,
            "comeback_wins_after_first_set_loss": comeback_wins_total,
            "observed_comeback_rate": rate(comeback_wins_total, comeback_total),
            "players_with_exposure": len(comeback_exposures),
            "support": _threshold_report(comeback_exposures),
            "profile_build_enabled": False,
            "predictive_signal_proven": False,
        },
        "bo5_stamina_readiness": {
            "exact_bo5_matches": bo5_exact,
            "player_match_exposures": int(counts["bo5_player_match_exposures"]),
            "late_set_player_exposures": int(counts["bo5_late_set_player_exposures"]),
            "players_with_bo5_match": len(bo5_matches),
            "players_with_late_set_exposure": len(bo5_late_sets),
            "match_support": _threshold_report(bo5_matches),
            "late_set_support": _threshold_report(bo5_late_sets),
            "profile_build_enabled": False,
            "predictive_signal_proven": False,
        },
        "readiness": {
            "exact_match_state_source_available": exact_matches > 0,
            "comeback_profile_design_sample_available": comeback_total >= 100,
            "bo5_stamina_profile_design_sample_available": (
                bo5_exact >= 50
                and int(counts["bo5_late_set_player_exposures"]) >= 200
            ),
            "profile_build_authorized": False,
            "training_join_authorized": False,
        },
        "production_influence": False,
        "runtime_scoring_enabled": False,
        "profile_build_enabled": False,
        "training_join_enabled": False,
        "simulator_callback_activation_enabled": False,
        "symphony2_influence": False,
        "superbet_playable_influence": False,
        "contract": {
            "pbp_native_provider_ids_only": True,
            "historical_csv_id_namespace_not_used": True,
            "name_or_fuzzy_join_forbidden": True,
            "latest_stats_score_must_match_final_tape_score": True,
            "legal_completed_match_score_required": True,
            "full_set_winner_sequence_from_zero_required": True,
            "atomic_plus_one_set_transitions_only": True,
            "retirement_or_incomplete_scores_rejected": True,
            "comeback_means_match_win_after_observed_first_set_loss": True,
            "bo5_stamina_evidence_uses_only_exact_completed_bo5": True,
            "profile_build_requires_separate_gate": True,
            "chronological_backtest_required_after_profile_gate": True,
        },
        "note": (
            "Readiness evidence only. Exact set-order proof is required because "
            "final score alone cannot prove comeback or late-set stamina semantics."
        ),
    }


def build() -> dict[str, Any]:
    payloads = []
    if CACHE.exists():
        for path in sorted(CACHE.glob("*.json.gz")):
            payload = _read(path)
            if payload is not None:
                payloads.append(payload)

    report = audit_payloads(payloads)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "version": report["version"],
        "matches_seen": report["matches_seen"],
        "exact_set_sequences": report["matches_with_exact_set_sequence"],
        "comeback_exposures": report["comeback_readiness"]["first_set_loss_player_exposures"],
        "bo5_exact_matches": report["bo5_stamina_readiness"]["exact_bo5_matches"],
        "comeback_design_sample": report["readiness"]["comeback_profile_design_sample_available"],
        "bo5_stamina_design_sample": report["readiness"]["bo5_stamina_profile_design_sample_available"],
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build()
