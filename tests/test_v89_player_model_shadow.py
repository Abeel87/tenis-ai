from pathlib import Path

from backend import player_model_shadow_v89 as shadow


def _profile(overall, serve, ret, form, mental=60, quality="HIGH"):
    return {
        "quality": quality,
        "sample_matches": 12,
        "coverage": 0.9,
        "fallback_used": False,
        "indexes": {
            "overall": overall,
            "serve": serve,
            "return": ret,
            "form": form,
            "mental": mental,
            "early": 70,
            "rank_strength": 65,
        },
        "windows": {
            "5": {"sample_matches": 5, "metrics": {}},
            "10": {
                "sample_matches": 10,
                "metrics": {
                    "hold_rate": {"adjusted": 0.80},
                    "break_rate": {"adjusted": 0.25},
                    "serve_points_won": {"adjusted": 0.64},
                    "return_points_won": {"adjusted": 0.40},
                    "first_set_won": {"adjusted": 0.62},
                    "won": {"adjusted": 0.60},
                },
            },
            "20": {"sample_matches": 12, "metrics": {}},
        },
    }


def test_feature_snapshot_is_directional_and_pre_match_only():
    match = {
        "p1": "Alpha",
        "p2": "Beta",
        "best_of": 3,
        "player_intelligence_v85": {
            "profiles": {
                "p1": _profile(72, 78, 66, 75),
                "p2": _profile(64, 68, 62, 60),
            },
            "matchup": {
                "quality": "HIGH",
                "best_of": 3,
                "edge_p1": 8,
                "serve_edge_p1": 16,
                "return_edge_p1": -2,
                "form_edge_p1": 15,
            },
        },
    }
    p1 = shadow.feature_snapshot(match, {"market": "match_winner", "pick": "Alpha"})
    p2 = shadow.feature_snapshot(match, {"market": "match_winner", "pick": "Beta"})
    assert p1["pick_side"] == "p1"
    assert p2["pick_side"] == "p2"
    assert p1["overall_edge_for_pick"] == 8
    assert p2["overall_edge_for_pick"] == -8
    assert p1["feature_coverage"] > 0.8


def test_split_by_match_never_leaks_same_match():
    rows = []
    for i in range(20):
        for j in range(2):
            rows.append({
                "match_key": f"m{i:02d}",
                "scheduled_time": f"2026-08-{i+1:02d}T10:00:00Z",
                "candidate_key": f"s{j}",
                "target": (i + j) % 2,
            })
    train, holdout = shadow.split_by_match(rows)
    assert train and holdout
    assert {r["match_key"] for r in train}.isdisjoint({r["match_key"] for r in holdout})


def test_old_player_rows_still_build_without_granular_snapshot():
    history = [{
        "match_id": 1,
        "scheduled_time": "2026-08-20T10:00:00Z",
        "tour": "ATP",
        "surface": "hard",
        "autolearn_signals_v84": [{
            "key": "match_win|alpha",
            "market": "match_winner",
            "pick": "Alpha",
            "model_scores": {"current": 70, "catboost": 68, "ensemble": 71},
            "result": "hit",
        }],
        "player_intelligence_signals_v85": [{
            "key": "match_win|alpha",
            "market": "match_winner",
            "pick": "Alpha",
            "player_probability": 73,
            "ensemble_base": 71,
            "shadow_score": 72,
            "support_score": 8,
            "quality": "HIGH",
            "result": "hit",
        }],
    }]
    rows = shadow.build_training_rows(history)
    assert len(rows) == 1
    assert rows[0]["player_probability"] == 73
    assert rows[0]["feature_coverage"] == 0
    assert rows[0]["ensemble_score"] == 71


def test_shadow_source_has_hard_production_boundary():
    src = Path(shadow.__file__).read_text(encoding="utf-8")
    assert 'MODE = "SHADOW"' in src
    assert '"production_influence": False' in src
    assert 'final_score"] =' not in src
    assert 'generator_selected"] =' not in src
