import pytest

from backend.player_dna_match_state_readiness import (
    MODE,
    _exact_set_winner_sequence,
    audit_payloads,
    inspect_payload,
)


def _payload(sequence, *, p1=101, p2=202, match_id="m1"):
    sets = [0, 0]
    tape = [
        {
            "sets": [0, 0],
            "games": [0, 0],
            "points": ["0", "0"],
        }
    ]
    for index, winner in enumerate(sequence, start=1):
        sets[winner - 1] += 1
        tape.append(
            {
                "sets": list(sets),
                "games": [6, 4],
                "points": ["0", "0"],
                "event_index": index,
            }
        )

    final_score = {
        "sets": list(sets),
        "games": [6, 4],
        "points": ["0", "0"],
    }
    return {
        "match": {
            "id": match_id,
            "scheduled_time": "2026-09-01T10:00:00Z",
            "surface": "hard",
            "players": {
                "p1": {"id": p1, "name": "Alpha"},
                "p2": {"id": p2, "name": "Beta"},
            },
        },
        "profiles": [
            {
                "created_at": "2026-09-01T13:00:00Z",
                "input_state": {
                    "score": final_score,
                    "stats": {"p1": {}, "p2": {}},
                },
            }
        ],
        "tape": tape,
    }


def test_exact_sequence_proves_comeback_only_from_atomic_set_order():
    payload = _payload([1, 2, 2])

    item = inspect_payload(payload)

    assert item["stable_identity"] is True
    assert item["terminal_score_match"] is True
    assert item["legal_completed_match"] is True
    assert item["exact_set_winner_sequence"] is True
    assert item["best_of"] == 3
    assert item["final_sets"] == [1, 2]
    assert item["set_winner_sequence"] == [1, 2, 2]
    assert item["first_set_winner_side"] == 1
    assert item["first_set_loser_side"] == 2
    assert item["match_winner_side"] == 2
    assert item["comeback_after_losing_first_set"] is True


def test_set_sequence_rejects_jump_even_when_final_score_is_legal():
    payload = _payload([1, 1])
    payload["tape"] = [
        {"sets": [0, 0], "games": [0, 0], "points": ["0", "0"]},
        {"sets": [2, 0], "games": [6, 4], "points": ["0", "0"]},
    ]

    assert _exact_set_winner_sequence(payload) is None
    item = inspect_payload(payload)
    assert item["terminal_score_match"] is True
    assert item["legal_completed_match"] is True
    assert item["exact_set_winner_sequence"] is False


def test_terminal_stats_score_mismatch_fails_before_match_state_use():
    payload = _payload([1, 2, 2])
    payload["profiles"][0]["input_state"]["score"]["sets"] = [1, 1]

    item = inspect_payload(payload)

    assert item["terminal_score_match"] is False
    assert "exact_set_winner_sequence" not in item


def test_audit_reports_comeback_and_exact_bo5_late_set_readiness_without_activation():
    bo3_comeback = _payload([1, 2, 2], match_id="bo3-comeback")
    bo3_straight = _payload([1, 1], p1=303, p2=404, match_id="bo3-straight")
    bo5 = _payload([1, 2, 1, 2, 1], p1=505, p2=606, match_id="bo5")

    report = audit_payloads([bo3_comeback, bo3_straight, bo5])

    assert report["mode"] == MODE
    assert report["matches_with_exact_set_sequence"] == 3
    assert report["format_coverage"]["bo3_exact_matches"] == 2
    assert report["format_coverage"]["bo5_exact_matches"] == 1

    comeback = report["comeback_readiness"]
    assert comeback["first_set_loss_player_exposures"] == 3
    assert comeback["comeback_wins_after_first_set_loss"] == 1
    assert comeback["observed_comeback_rate"] == pytest.approx(1 / 3, abs=1e-6)
    assert comeback["profile_build_enabled"] is False
    assert comeback["predictive_signal_proven"] is False

    stamina = report["bo5_stamina_readiness"]
    assert stamina["exact_bo5_matches"] == 1
    assert stamina["player_match_exposures"] == 2
    assert stamina["late_set_player_exposures"] == 6
    assert stamina["players_with_bo5_match"] == 2
    assert stamina["players_with_late_set_exposure"] == 2
    assert stamina["profile_build_enabled"] is False
    assert stamina["predictive_signal_proven"] is False

    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["profile_build_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["simulator_callback_activation_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False


def test_audit_contract_requires_full_set_order_proof_and_separate_gate():
    report = audit_payloads([])
    contract = report["contract"]

    assert contract["pbp_native_provider_ids_only"] is True
    assert contract["historical_csv_id_namespace_not_used"] is True
    assert contract["name_or_fuzzy_join_forbidden"] is True
    assert contract["latest_stats_score_must_match_final_tape_score"] is True
    assert contract["legal_completed_match_score_required"] is True
    assert contract["full_set_winner_sequence_from_zero_required"] is True
    assert contract["atomic_plus_one_set_transitions_only"] is True
    assert contract["retirement_or_incomplete_scores_rejected"] is True
    assert contract["profile_build_requires_separate_gate"] is True
    assert contract["chronological_backtest_required_after_profile_gate"] is True
