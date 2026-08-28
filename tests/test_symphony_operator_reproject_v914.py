from backend.symphony_operator_reproject_v914 import reproject_match


def _result_match():
    canonical = [
        {
            "market": "set1_tiebreak",
            "pick": "no",
            "operator_available": True,
        },
        {
            "market": "match_total",
            "pick": "over",
            "line": 20.5,
            "operator_available": True,
        },
    ]
    model_signals = [
        {
            "market": "set1_tiebreak",
            "pick": "no",
            "operator_line_verified": True,
            "score": 84.0,
            "label": "Tie-break w 1. secie · NIE",
            "key": "set1_tiebreak|no",
        },
        {
            "market": "match_total",
            "pick": "over",
            "line": 20.5,
            "operator_line_verified": True,
            "score": 78.0,
            "label": "Mecz O20.5",
            "key": "match_total|20.5|over",
        },
    ]
    return {
        "id": 1,
        "superbet_market_v91": {
            "operator_verified": True,
            "status": "VERIFIED",
            "canonical_selections": canonical,
            "model_signals": model_signals,
        },
    }


def test_promotes_playable_alternative_without_rerunning_symphony():
    report_match = {
        "id": 1,
        "recommended_leg_count": 2,
        "compositions": {
            "2": {
                "legs": 2,
                "symphony_score": 91.0,
                "selection": [
                    {"market": "set1_tiebreak", "pick": "no", "label": "TB NIE"},
                    {"market": "match_total", "pick": "over", "line": 18.5, "label": "O18.5"},
                ],
                "alternatives": [
                    {
                        "legs": 2,
                        "symphony_score": 87.0,
                        "selection": [
                            {"market": "set1_tiebreak", "pick": "no", "label": "TB NIE"},
                            {"market": "match_total", "pick": "over", "line": 20.5, "label": "O20.5"},
                        ],
                    }
                ],
            }
        },
    }

    out, info = reproject_match(report_match, _result_match())
    comp = out["compositions"]["2"]

    assert info["active"] is True
    assert out["recommended_leg_count"] == 2
    assert [x.get("line") for x in comp["selection"] if x.get("market") == "match_total"] == [20.5]
    assert all(x.get("line") != 18.5 for x in comp["selection"])
    assert comp["operator_reprojected"] is True
    assert comp["selection"][1]["operator_line_verified"] is True
    assert out["operator_reprojection"]["full_scenario_search_rerun"] is False


def test_unavailable_player_prop_cannot_survive_playable_composition():
    report_match = {
        "id": 1,
        "recommended_leg_count": 2,
        "compositions": {
            "2": {
                "legs": 2,
                "symphony_score": 80.0,
                "selection": [
                    {"market": "set1_tiebreak", "pick": "no"},
                    {"market": "player_aces", "pick": "over", "line": 4.5, "player": "Player A"},
                ],
            }
        },
    }

    out, _ = reproject_match(report_match, _result_match())

    assert out["compositions"] == {}
    assert out["recommended_leg_count"] is None
    assert out["operator_reprojection"]["status"] == "NO_PLAYABLE_COMPOSITION"


def test_no_verified_operator_match_keeps_analysis_report_untouched():
    report_match = {
        "id": 1,
        "recommended_leg_count": 2,
        "compositions": {"2": {"selection": [{"market": "match_total", "pick": "over", "line": 18.5}]}},
    }

    out, info = reproject_match(report_match, {"id": 1})

    assert info["active"] is False
    assert out["compositions"] == report_match["compositions"]
    assert out["operator_reprojection"]["status"] == "NO_VERIFIED_OPERATOR_MATCH"
