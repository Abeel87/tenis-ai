from backend.player_dna_pressure_challenger import (
    EARLY_GAME_DIAGNOSTIC_NUMERIC,
    PRESSURE_PRIMARY_NUMERIC,
    evaluate,
    enrich_feature_rows,
)


def _prior(
    matches,
    *,
    serve=0.64,
    ret=0.38,
    hold=0.80,
    brk=0.20,
    bp_save=0.61,
    bp_conv=0.39,
    early_shift=0.0,
):
    row = {
        "matches": matches,
        "serve_win_rate": serve if matches else None,
        "return_win_rate": ret if matches else None,
        "hold_rate": hold if matches else None,
        "break_rate": brk if matches else None,
        "bp_save_rate": bp_save if matches else None,
        "bp_conversion_rate": bp_conv if matches else None,
    }
    for index in (1, 2, 3):
        row[f"early_service_game_{index}_hold_rate"] = (
            min(1.0, hold + early_shift + index * 0.01) if matches else None
        )
        row[f"early_return_game_{index}_break_rate"] = (
            min(1.0, brk + early_shift + index * 0.01) if matches else None
        )
    return row


def _rolling(*, hold, brk, bp_save, bp_conv, early_shift=0.0):
    return {
        "windows": {
            "L5": _prior(
                5,
                hold=hold,
                brk=brk,
                bp_save=bp_save,
                bp_conv=bp_conv,
                early_shift=early_shift,
            ),
            "L10": _prior(
                10,
                hold=hold - 0.01,
                brk=brk - 0.01,
                bp_save=bp_save - 0.01,
                bp_conv=bp_conv - 0.01,
                early_shift=early_shift,
            ),
            "L20": _prior(
                20,
                hold=hold - 0.02,
                brk=brk - 0.02,
                bp_save=bp_save - 0.02,
                bp_conv=bp_conv - 0.02,
                early_shift=early_shift,
            ),
        },
        "trend": {},
    }


def _profile(match_id, when, player, opponent, *, serverish):
    if serverish:
        overall = _prior(
            8,
            serve=0.68,
            ret=0.36,
            hold=0.84,
            brk=0.18,
            bp_save=0.66,
            bp_conv=0.35,
            early_shift=0.01,
        )
        surface = _prior(
            6,
            serve=0.67,
            ret=0.35,
            hold=0.82,
            brk=0.17,
            bp_save=0.64,
            bp_conv=0.34,
            early_shift=0.02,
        )
        rolling_all = _rolling(
            hold=0.86,
            brk=0.19,
            bp_save=0.68,
            bp_conv=0.36,
            early_shift=0.03,
        )
        rolling_surface = _rolling(
            hold=0.85,
            brk=0.18,
            bp_save=0.67,
            bp_conv=0.35,
            early_shift=0.04,
        )
    else:
        overall = _prior(
            9,
            serve=0.62,
            ret=0.42,
            hold=0.76,
            brk=0.24,
            bp_save=0.59,
            bp_conv=0.43,
            early_shift=0.01,
        )
        surface = _prior(
            7,
            serve=0.61,
            ret=0.43,
            hold=0.75,
            brk=0.26,
            bp_save=0.58,
            bp_conv=0.45,
            early_shift=0.02,
        )
        rolling_all = _rolling(
            hold=0.77,
            brk=0.28,
            bp_save=0.60,
            bp_conv=0.47,
            early_shift=0.03,
        )
        rolling_surface = _rolling(
            hold=0.76,
            brk=0.29,
            bp_save=0.59,
            bp_conv=0.48,
            early_shift=0.04,
        )

    return {
        "target_match_id": match_id,
        "target_scheduled_time": when,
        "target_surface": "hard",
        "player_id": player,
        "opponent_id": opponent,
        "strict_as_of": True,
        "same_time_matches_count_as_prior": False,
        "overall_prior": overall,
        "same_surface_prior": surface,
        "rolling_prior": {
            "all_surface": rolling_all,
            "same_surface": {"surface": "hard", **rolling_surface},
        },
    }


def _point(match_id, when):
    return {
        "match_id": match_id,
        "event_index": 0,
        "match_scheduled_time": when,
        "surface": "hard",
        "tour": "ATP",
        "match_format": "BO3",
        "context_ready_player_point": True,
        "server_player_id": 1,
        "receiver_player_id": 2,
        "server_won": True,
        "server_ranking": 20,
        "receiver_ranking": 40,
        "is_tiebreak_before": False,
    }


def test_pressure_enrichment_uses_canonical_overall_surface_and_rolling_profiles():
    when = "2026-09-06T10:00:00Z"
    profiles = [
        _profile("m1", when, 1, 2, serverish=True),
        _profile("m1", when, 2, 1, serverish=False),
    ]
    rows, counts = enrich_feature_rows([_point("m1", when)], profiles)

    assert len(rows) == 1
    row = rows[0]
    assert row["server_overall_hold_rate"] == 0.84
    assert row["server_surface_bp_save_rate"] == 0.64
    assert row["receiver_overall_break_rate"] == 0.24
    assert row["receiver_surface_bp_conversion_rate"] == 0.45
    assert row["server_all_l5_hold_rate"] == 0.86
    assert row["receiver_surface_l20_break_rate"] == 0.27
    assert row["server_all_l5_early_service_game_1_hold_rate"] == 0.90
    assert row["receiver_surface_l5_early_return_game_3_break_rate"] == 0.36
    assert counts["enrichment_counts"]["enriched_rows"] == 1
    assert counts["enrichment_counts"]["rows_with_any_primary_pressure_rate"] == 1
    assert counts["enrichment_counts"]["rows_with_any_early_game_rate"] == 1


def test_primary_pressure_gate_excludes_early_game_and_support_proxy_features():
    primary = set(PRESSURE_PRIMARY_NUMERIC)
    early = set(EARLY_GAME_DIAGNOSTIC_NUMERIC)

    assert len(primary) == 32
    assert len(early) == 48
    assert primary.isdisjoint(early)
    assert all("hold_rate" in name or "break_rate" in name or "bp_" in name for name in primary)
    assert all("early_service_game_" in name or "early_return_game_" in name for name in early)
    assert all("support" not in name for name in primary | early)


def test_early_game_is_explicitly_diagnostic_only_even_without_enough_sample():
    report = evaluate([])
    contract = report["pressure_contract"]
    signal = report["signal"]

    assert report["mode"] == "SHADOW_PRESSURE_CHALLENGER_EVAL_ONLY"
    assert report["production_influence"] is False
    assert report["runtime_scoring_enabled"] is False
    assert report["training_join_enabled"] is False
    assert report["canonical_profile_write_enabled"] is False
    assert report["symphony2_influence"] is False
    assert report["superbet_playable_influence"] is False
    assert report["auto_promote"] is False
    assert contract["primary_family"] == "hold_break_plus_break_point"
    assert contract["early_game_is_diagnostic_only"] is True
    assert contract["early_game_cannot_make_primary_gate_pass"] is True
    assert contract["primary_raw_support_counts_are_features"] is False
    assert signal["early_game_diagnostic_affects_primary_signal"] is False
    assert signal["status"] == "INSUFFICIENT_SHADOW_SAMPLE"
