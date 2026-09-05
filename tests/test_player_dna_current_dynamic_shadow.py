from datetime import datetime, timezone

import backend.player_dna_current_dynamic_shadow as dynamic


def _simulation(p1_match=0.6, p1_set=0.58, tiebreak=0.22, over=0.7, early=0.8):
    return {
        "match": {"p1_win": p1_match},
        "first_set": {
            "p1_win": p1_set,
            "tiebreak": tiebreak,
            "over": {
                "8.5": over,
                "9.5": over - 0.1,
                "10.5": over - 0.2,
                "11.5": over - 0.3,
                "12.5": over - 0.4,
            },
        },
        "early_equal_score": {
            "1:1": early,
            "2:2": early - 0.1,
            "3:3": early - 0.2,
        },
        "dynamic_callback_unique_states": 10,
        "dynamic_hold_cache_states": 5,
        "dynamic_set_cache_states": 3,
    }


def _consensus():
    markets = {
        market: {"decision": "INSUFFICIENT_OR_MIXED"}
        for market in dynamic.BINARY_MARKETS
    }
    markets["match_p1_win"] = {"decision": "CONSENSUS_DYNAMIC_CANDIDATE"}
    markets["first_set_p1_win"] = {"decision": "CONFLICT"}
    markets["first_set_tiebreak"] = {"decision": "CONSENSUS_PROFILE_REFERENCE"}
    return {
        "segment_consensus_shadow_policy": {
            "mode": "SHADOW_SEGMENT_CONSENSUS_DIAGNOSTIC_ONLY",
            "production_influence": False,
            "runtime_switch_enabled": False,
            "auto_promote": False,
            "prospective_validation_required": True,
            "segments": {
                "challenger|hard": {
                    "markets": markets,
                }
            },
        }
    }


def test_segment_market_policy_blocks_unknown_or_conflicting_segments():
    policy = dynamic.segment_market_policy(
        _consensus(),
        tour="CHALLENGER",
        surface="HARD",
    )
    assert policy["match_p1_win"] == "CONSENSUS_DYNAMIC_CANDIDATE"
    assert policy["first_set_p1_win"] == "CONFLICT"
    assert policy["first_set_tiebreak"] == "CONSENSUS_PROFILE_REFERENCE"

    missing = dynamic.segment_market_policy(
        _consensus(),
        tour="WTA",
        surface="clay",
    )
    assert set(missing.values()) == {"INSUFFICIENT_OR_MIXED"}


def test_current_dynamic_shadow_reuses_historical_candidate_and_never_runtime_switches(monkeypatch):
    cutoff = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    feature_row = {
        "match_id": "old",
        "scheduled_time": datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc),
        "server_overall_matches": 5,
        "receiver_overall_matches": 5,
        "server_won": 1,
    }
    monkeypatch.setattr(dynamic, "build_feature_rows", lambda points, profiles: ([feature_row], {"joined_rows": 1}))
    monkeypatch.setattr(
        dynamic,
        "_fit_logistic_newton",
        lambda frame, numeric: {"converged": True, "schema": {}, "beta": [], "feature_names": []},
    )
    monkeypatch.setattr(
        dynamic,
        "_model_meta",
        lambda model: {"converged": True, "model_fingerprint_sha256": "lean-fingerprint"},
    )

    current_profiles = [
        {
            "target_match_id": "m1",
            "player_side": "p1",
            "target_surface": "hard",
            "target_tour": "CHALLENGER",
            "target_format": "BO3",
            "overall_prior": {"matches": 5},
            "same_surface_prior": {"matches": 5},
        },
        {
            "target_match_id": "m1",
            "player_side": "p2",
            "target_surface": "hard",
            "target_tour": "CHALLENGER",
            "target_format": "BO3",
            "overall_prior": {"matches": 5},
            "same_surface_prior": {"matches": 5},
        },
    ]
    monkeypatch.setattr(
        dynamic,
        "build_current_target_profiles",
        lambda points, targets: (current_profiles, {"targets_seen": 1}),
    )
    monkeypatch.setattr(dynamic, "simulate_match", lambda *args, **kwargs: _simulation(p1_match=0.55, p1_set=0.52, tiebreak=0.18))
    monkeypatch.setattr(
        dynamic,
        "_dynamic_candidate_simulation",
        lambda *args, **kwargs: _simulation(p1_match=0.65, p1_set=0.62, tiebreak=0.25),
    )

    current = {
        "mode": "SHADOW_CURRENT_ONLY",
        "training_cutoff_exclusive": cutoff.isoformat(),
        "matches": [{
            "match_id": "m1",
            "scheduled_time": "2026-09-05T14:00:00Z",
            "tour": "challenger",
            "surface": "hard",
            "best_of": 3,
            "p1": "A",
            "p2": "B",
            "p1_id": 1,
            "p2_id": 2,
            "p1_rank": 40,
            "p2_rank": 60,
            "status": "SHADOW_SCORED",
            "p1_serve_point_win_probability": 0.62,
            "p2_serve_point_win_probability": 0.60,
        }],
    }

    report = dynamic.build_current_dynamic_shadow([], [], current, _consensus())
    assert report["status"] == "ACTIVE_SHADOW"
    assert report["production_influence"] is False
    assert report["runtime_switch_enabled"] is False
    assert report["auto_promote"] is False
    assert report["prospective_validation_required"] is True
    assert report["feature_groups"] == ["profile", "rank", "point_pressure", "set_match_state"]

    row = report["matches"][0]
    assert row["status"] == "DYNAMIC_SHADOW_SCORED"
    markets = row["markets"]
    assert markets["match_p1_win"]["decision"] == "CONSENSUS_DYNAMIC_CANDIDATE"
    assert markets["match_p1_win"]["dynamic_candidate_probability"] == 0.65
    assert markets["match_p1_win"]["shadow_policy_probability"] == 0.65

    assert markets["first_set_tiebreak"]["decision"] == "CONSENSUS_PROFILE_REFERENCE"
    assert markets["first_set_tiebreak"]["profile_reference_probability"] == 0.18
    assert markets["first_set_tiebreak"]["shadow_policy_probability"] == 0.18

    assert markets["first_set_p1_win"]["decision"] == "CONFLICT"
    assert markets["first_set_p1_win"]["shadow_policy_probability"] is None


def test_current_dynamic_shadow_requires_both_provider_ranks(monkeypatch):
    current = {
        "mode": "SHADOW_CURRENT_ONLY",
        "training_cutoff_exclusive": "2026-09-05T12:00:00+00:00",
        "matches": [{
            "match_id": "m1",
            "tour": "challenger",
            "surface": "hard",
            "status": "SHADOW_SCORED",
            "p1_rank": 40,
            "p2_rank": None,
        }],
    }
    monkeypatch.setattr(
        dynamic,
        "build_feature_rows",
        lambda points, profiles: ([{
            "match_id": "old",
            "scheduled_time": datetime(2026, 9, 4, tzinfo=timezone.utc),
            "server_overall_matches": 5,
            "receiver_overall_matches": 5,
            "server_won": 1,
        }], {}),
    )
    monkeypatch.setattr(
        dynamic,
        "_fit_logistic_newton",
        lambda frame, numeric: {"converged": True, "schema": {}, "beta": [], "feature_names": []},
    )
    monkeypatch.setattr(dynamic, "_model_meta", lambda model: {"converged": True})
    monkeypatch.setattr(dynamic, "build_current_target_profiles", lambda points, targets: ([], {}))

    report = dynamic.build_current_dynamic_shadow([], [], current, _consensus())
    assert report["matches"][0]["status"] == "BLOCKED_MISSING_PROVIDER_RANK"
    assert report["runtime_switch_enabled"] is False
