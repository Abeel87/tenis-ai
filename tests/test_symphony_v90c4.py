from backend.symphony_c4 import (
    augment_match_c4,
    comparison_compatible,
    coverage_first_metrics,
    leg_count_intelligence,
    serve_comparison_signals,
    three_way_poisson,
)
from backend.symphony_engine_v90 import Candidate
from backend.symphony_engine_v90c import build_report


def _serve_match():
    return {
        "id": 904,
        "p1": "Server A",
        "p2": "Server B",
        "best_of": 3,
        "service_model": {"p1_hold": 80, "p2_hold": 76},
        "game_states": {
            "2": {"2:0": 22, "1:1": 62, "0:2": 16},
            "4": {"4:0": 5, "3:1": 18, "2:2": 55, "1:3": 16, "0:4": 6},
            "6": {"6:0": 1, "5:1": 6, "4:2": 18, "3:3": 50, "2:4": 17, "1:5": 6, "0:6": 2},
        },
        "match_win": {"Server A": 64, "Server B": 36},
        "first_set_win": {"Server A": 60, "Server B": 40},
        "second_set_win": {"Server A": 58, "Server B": 42},
        "third_set_win": {"Server A": 57, "Server B": 43},
        "over_under": {
            "8.5": {"over": 79, "under": 21},
            "9.5": {"over": 61, "under": 39},
            "10.5": {"over": 40, "under": 60},
        },
        "match_over_under": {
            "20.5": {"over": 66, "under": 34},
            "21.5": {"over": 57, "under": 43},
        },
        "exact_first_set": {
            "6:3": 18, "6:4": 18, "7:5": 12, "7:6": 12,
            "3:6": 12, "4:6": 12, "5:7": 9, "6:7": 7,
        },
        "exact_match_score": {"2:0": 36, "2:1": 28, "1:2": 21, "0:2": 15},
        "total_sets": {"2 sety": 51, "3 sety": 49},
        "serve_props_v72": {
            "ready": True,
            "p1": {
                "aces": {
                    "ready": True,
                    "mean": 10.0,
                    "lines": {"8.5": {"over": 67, "under": 33}},
                },
                "double_faults": {
                    "ready": True,
                    "mean": 4.0,
                    "lines": {"3.5": {"over": 54, "under": 46}},
                },
            },
            "p2": {
                "aces": {
                    "ready": True,
                    "mean": 4.0,
                    "lines": {"3.5": {"over": 57, "under": 43}},
                },
                "double_faults": {
                    "ready": True,
                    "mean": 2.0,
                    "lines": {"1.5": {"over": 59, "under": 41}},
                },
            },
        },
        "autolearn_v84": {"signals": []},
    }


def _candidate(key, market, pick):
    return Candidate(
        key=key,
        label=key,
        market=market,
        pick=pick,
        line=None,
        checkpoint=None,
        prod_score=70,
        shadow_scores={},
        path_probability=None,
        evidence_score=70,
        agreement=0.5,
        conflict=0.0,
    )


def test_three_way_poisson_is_normalized_and_favours_bigger_mean():
    probs = three_way_poisson(10.0, 4.0)
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    assert probs["p1"] > probs["draw"]
    assert probs["p1"] > probs["p2"]


def test_serve_comparison_signals_have_three_families_and_a_draw_option():
    rows = serve_comparison_signals(_serve_match())
    assert len(rows) == 9
    markets = {row["market"] for row in rows}
    assert markets == {"most_aces", "most_double_faults", "most_aces_plus_df"}

    for market in markets:
        family = [row for row in rows if row["market"] == market]
        assert {row["pick"] for row in family} == {"Server A", "draw", "Server B"}
        assert abs(sum(row["symphony_raw_probability"] for row in family) - 100.0) < 0.02
        assert all(row["exact_path_supported"] is False for row in family)


def test_c4_augmentation_is_read_only_and_adds_comparison_evidence():
    source = _serve_match()
    assert source["autolearn_v84"]["signals"] == []
    augmented, meta = augment_match_c4(source)
    assert source["autolearn_v84"]["signals"] == []
    assert meta["serve_comparison_added"] == 9
    assert meta["families"]["most_aces"] == 3
    assert meta["families"]["most_double_faults"] == 3
    assert meta["families"]["most_aces_plus_df"] == 3
    assert any(x.get("market") == "most_aces_plus_df" for x in augmented["autolearn_v84"]["signals"])


def test_coverage_first_ranking_penalizes_zero_coverage():
    def base_metrics(match, combo, outcomes):
        coverage = 1.0 if combo == "full" else 0.0
        return {
            "score": 90.0,
            "path_coverage": coverage,
            "supported_legs": 2 if coverage else 0,
            "joint_supported_only": 0.55 if coverage else None,
            "avg_evidence": 90.0,
            "agreement": 0.5,
            "conflict": 0.0,
            "joint": 0.55 if coverage else None,
        }

    wrapped = coverage_first_metrics(base_metrics)
    full = wrapped(None, "full", None)
    unsupported = wrapped(None, "unsupported", None)
    assert full["score"] > unsupported["score"]
    assert full["coverage_adjustment"] > 0
    assert unsupported["coverage_adjustment"] <= -28


def test_comparison_market_outcomes_are_mutually_exclusive():
    compatible = comparison_compatible(lambda a, b: True)
    a = _candidate("most_aces|A", "most_aces", "Server A")
    draw = _candidate("most_aces|draw", "most_aces", "draw")
    other_family = _candidate("most_df|A", "most_double_faults", "Server A")
    assert compatible(a, draw) is False
    assert compatible(a, other_family) is True


def test_leg_count_intelligence_can_choose_four_instead_of_always_two():
    match = {
        "compositions": {
            "2": {"symphony_score": 91.0, "path_coverage": 1.0, "joint_probability": 70.0, "fragility": [{"fragility": 5}]},
            "3": {"symphony_score": 91.0, "path_coverage": 1.0, "joint_probability": 60.0, "fragility": [{"fragility": 6}]},
            "4": {"symphony_score": 90.5, "path_coverage": 1.0, "joint_probability": 50.0, "fragility": [{"fragility": 7}]},
            "5": {"symphony_score": 74.0, "path_coverage": 0.5, "joint_probability": None, "fragility": [{"fragility": 20}]},
            "6": {"symphony_score": 68.0, "path_coverage": 0.33, "joint_probability": None, "fragility": [{"fragility": 27}]},
        }
    }
    result = leg_count_intelligence(match)
    assert result["recommended"] == 4
    assert result["historical_learning_active"] is False
    assert len(result["options"]) == 5
    assert next(x for x in result["options"] if x["legs"] == 5)["eligible"] is False


def test_c4_features_remain_present_in_v90d_report(monkeypatch):
    match = _serve_match()

    def fake_read(path, fallback):
        if path.name == "results.json":
            return [match]
        return {}

    monkeypatch.setattr("backend.symphony_engine_v90._read", fake_read)
    report = build_report(legs=4)
    assert report["version"] == "v9.0D.1"
    assert report["production_influence"] is False
    assert report["contract"]["coverage_first_ranking"] is True
    assert report["contract"]["serve_comparisons_are_evidence_only"] is True
    assert report["contract"]["auto_leg_count_2_to_6"] is True
    assert report["contract"]["historical_leg_count_learning_guarded"] is True
    assert report["contract"]["historical_leg_count_learning_active"] is False
    assert report["matches_count"] == 1
    row = report["matches"][0]
    assert row["recommended_leg_count"] in {2, 3, 4, 5, 6}
    assert row["market_adapter"]["serve_comparison_added"] == 9
