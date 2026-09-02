from backend.shadow_promotion_gate_v942 import build_report


def _entry(result, sid, ensemble, adaptive, shadow):
    return {
        "playable_autolearn_signals_v912": [{
            "id": sid,
            "result": result,
            "model_scores": {"ensemble": ensemble},
            "adaptive_prod_v79": {"final_score": adaptive},
        }],
        "playable_shadow_models_v912": [{
            "id": sid,
            "result": result,
            "source_model": "ensemble_player_elo",
            "score": shadow,
        }],
    }


def test_gate_never_auto_promotes_even_when_evidence_is_strong():
    history = []
    # 260 common events: candidate selects all and wins 82%; ensemble selects 200
    # weaker events.  Add enough candidate-only observations for the canary gate.
    for i in range(260):
        hit = i % 100 < 82
        result = "hit" if hit else "miss"
        ensemble = 70.0 if i < 200 else 64.0
        adaptive = 69.0 if i < 190 else 63.0
        shadow = 74.0 if hit else 69.0
        history.append(_entry(result, f"s{i}", ensemble, adaptive, shadow))

    playable_stats = {"models": {"shadow_ensemble_player_elo": {
        "settled": 429, "hits": 355, "misses": 74, "accuracy": 82.8, "threshold": 68.0
    }}}
    surface_elo = {
        "holdout": {"ensemble_player_elo": {"n": 198, "accuracy": 73.9, "brier": 0.20561, "log_loss": 0.60213}},
        "gates": {"ensemble_player_elo": {
            "status": "promising", "accuracy_delta_pp": 1.7,
            "brier_gain": 0.00157, "log_loss_gain": 0.00343,
        }},
    }
    report = build_report(history, playable_stats, surface_elo)
    assert report["production_influence"] is False
    assert report["auto_promote"] is False
    assert report["candidate"] == "ensemble_player_elo"
    assert report["same_universe_comparisons"]["ensemble"]["common_settled"] == 260


def test_gate_stays_watch_on_small_sample():
    history = [_entry("hit", "one", 70.0, 70.0, 75.0)]
    report = build_report(history, {"models": {}}, {"holdout": {}, "gates": {}})
    assert report["status"] == "WATCH"
    assert report["next_step"] == "KEEP_SHADOW_AND_COLLECT"
    assert report["production_influence"] is False
