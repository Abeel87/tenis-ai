from backend.player_dna_match_state_profiles import (
    MODE,
    _contributions,
    _project,
    build_snapshots_from_payloads,
)
from backend.player_dna_match_state_readiness import inspect_payload


def _payload(
    sequence,
    *,
    match_id,
    scheduled,
    p1=101,
    p2=202,
    surface="hard",
    match_format=None,
):
    sets = [0, 0]
    tape = [
        {
            "sets": [0, 0],
            "games": [0, 0],
            "points": ["0", "0"],
        }
    ]
    for winner in sequence:
        sets[winner - 1] += 1
        tape.append(
            {
                "sets": list(sets),
                "games": [6, 4],
                "points": ["0", "0"],
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
            "scheduled_time": scheduled,
            "surface": surface,
            "format": match_format or ("BO5" if max(sets) == 3 else "BO3"),
            "status": "completed",
            "outcome": "completed",
            "event_status": "Finished",
            "winner": sequence[-1],
            "withdrew": None,
            "score": final_score,
            "players": {
                "p1": {"id": p1, "name": "Alpha"},
                "p2": {"id": p2, "name": "Beta"},
            },
        },
        "profiles": [],
        "tape": tape,
    }


def _snapshot(snapshots, match_id, player_id):
    return next(
        row
        for row in snapshots
        if row["target_match_id"] == match_id
        and row["player_id"] == player_id
    )


def test_comeback_and_front_runner_counts_are_exact_observed_outcomes():
    item = inspect_payload(
        _payload(
            [1, 2, 2],
            match_id="m1",
            scheduled="2026-09-01T10:00:00Z",
        )
    )
    contrib = _contributions(item)

    p1 = _project(contrib[101])
    p2 = _project(contrib[202])

    assert p1["first_set_win_exposures"] == 1
    assert p1["match_wins_after_first_set_win"] == 0
    assert p1["front_runner_conversion_rate"] == 0.0
    assert p1["first_set_loss_exposures"] == 0
    assert p1["comeback_rate_after_first_set_loss"] is None

    assert p2["first_set_loss_exposures"] == 1
    assert p2["comeback_wins_after_first_set_loss"] == 1
    assert p2["comeback_rate_after_first_set_loss"] == 1.0
    assert p2["first_set_win_exposures"] == 0


def test_bo5_late_and_deciding_set_counts_use_set_three_plus_and_set_five_only():
    item = inspect_payload(
        _payload(
            [1, 2, 1, 2, 1],
            match_id="bo5",
            scheduled="2026-09-01T10:00:00Z",
        )
    )
    contrib = _contributions(item)

    p1 = _project(contrib[101])
    p2 = _project(contrib[202])

    assert p1["bo5_matches"] == 1
    assert p2["bo5_matches"] == 1
    assert p1["bo5_late_set_exposures"] == 3
    assert p2["bo5_late_set_exposures"] == 3
    assert p1["bo5_late_set_wins"] == 2
    assert p2["bo5_late_set_wins"] == 1
    assert p1["bo5_late_set_win_rate"] == 2 / 3
    assert p2["bo5_late_set_win_rate"] == 1 / 3
    assert p1["bo5_deciding_set_exposures"] == 1
    assert p2["bo5_deciding_set_exposures"] == 1
    assert p1["bo5_deciding_set_wins"] == 1
    assert p2["bo5_deciding_set_wins"] == 0


def test_profiles_are_strict_as_of_and_never_see_the_target_match():
    first = _payload(
        [1, 2, 2],
        match_id="m1",
        scheduled="2026-09-01T10:00:00Z",
    )
    second = _payload(
        [2, 1, 1],
        match_id="m2",
        scheduled="2026-09-02T10:00:00Z",
    )

    snapshots, summary = build_snapshots_from_payloads([first, second])

    first_p2 = _snapshot(snapshots, "m1", 202)
    second_p2 = _snapshot(snapshots, "m2", 202)

    assert first_p2["overall_prior"]["matches"] == 0
    assert first_p2["overall_prior"]["first_set_loss_exposures"] == 0

    # P2 lost set 1 and came back in m1, so only the later target can see it.
    assert second_p2["overall_prior"]["matches"] == 1
    assert second_p2["overall_prior"]["first_set_loss_exposures"] == 1
    assert second_p2["overall_prior"]["comeback_wins_after_first_set_loss"] == 1
    assert second_p2["overall_prior"]["comeback_rate_after_first_set_loss"] == 1.0

    assert summary["strict_as_of_policy"] == (
        "source_match_scheduled_time < target_match_scheduled_time"
    )
    assert summary["same_time_matches_count_as_prior"] is False


def test_same_timestamp_matches_never_count_as_prior():
    a = _payload(
        [1, 2, 2],
        match_id="a",
        scheduled="2026-09-01T10:00:00Z",
        p1=101,
        p2=202,
    )
    b = _payload(
        [2, 1, 1],
        match_id="b",
        scheduled="2026-09-01T10:00:00Z",
        p1=101,
        p2=303,
    )

    snapshots, summary = build_snapshots_from_payloads([a, b])

    for row in snapshots:
        assert row["overall_prior"]["matches"] == 0
        assert row["same_surface_prior"]["matches"] == 0

    assert summary["same_time_groups"] == 1
    assert summary["contract"]["same_timestamp_matches_never_count_as_prior"] is True


def test_nonterminal_or_nonexact_payload_is_rejected_from_profile_source():
    good = _payload(
        [1, 1],
        match_id="good",
        scheduled="2026-09-01T10:00:00Z",
    )
    bad = _payload(
        [1, 1],
        match_id="bad",
        scheduled="2026-09-02T10:00:00Z",
    )
    bad["match"]["status"] = "live"

    snapshots, summary = build_snapshots_from_payloads([good, bad])

    assert len(snapshots) == 2
    assert {row["target_match_id"] for row in snapshots} == {"good"}
    assert summary["source_counts"]["payloads_seen"] == 2
    assert summary["source_counts"]["usable_exact_source_matches"] == 1
    assert (
        summary["source_counts"]["payloads_rejected_by_exact_match_state_gate"]
        == 1
    )


def test_profile_contract_is_shadow_only_and_bo5_rate_is_not_called_validated_stamina():
    _, summary = build_snapshots_from_payloads([])
    contract = summary["contract"]

    assert summary["mode"] == MODE
    assert summary["production_influence"] is False
    assert summary["runtime_scoring_enabled"] is False
    assert summary["training_join_enabled"] is False
    assert summary["canonical_point_scorer_feature_activation_enabled"] is False
    assert summary["simulator_callback_activation_enabled"] is False
    assert summary["symphony2_influence"] is False
    assert summary["superbet_playable_influence"] is False

    assert contract["provider_terminal_exact_set_order_source_only"] is True
    assert contract["stable_provider_ids_only"] is True
    assert contract["historical_csv_id_namespace_not_used"] is True
    assert contract["name_or_fuzzy_join_forbidden"] is True
    assert contract["strictly_prior_matches_only"] is True
    assert contract["raw_support_counts_accompany_every_rate"] is True
    assert contract["bo5_late_set_rate_is_descriptive_proxy_not_validated_stamina"] is True
    assert contract["no_shrinkage_or_partial_pooling_applied"] is True
    assert contract["no_profile_threshold_activation"] is True
    assert contract["predictive_signal_not_yet_proven"] is True
    assert contract["chronological_challenger_required_before_feature_activation"] is True
