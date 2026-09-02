from backend.pbp_market_evidence import build_market_evidence, enrich_market_evidence


def _metric(n, pct):
    return {"hits": int(round(n * pct / 100.0)), "n": n, "pct": pct}


def _profile(**overrides):
    metrics = {
        "hold1": _metric(5, 80),
        "hold2": _metric(5, 76),
        "hold3": _metric(2, 50),  # deliberately insufficient
        "after2_11": _metric(5, 72),
        "after4_22": _metric(5, 64),
        "after6_33": _metric(2, 50),  # deliberately insufficient
        "sequence_11_22_33": _metric(2, 50),
        "set1_win": _metric(5, 60),
        "set1_over_8.5": _metric(5, 84),
        "set1_over_9.5": _metric(5, 62),
    }
    metrics.update(overrides)
    return {"ready": False, "pbp_tendencies": {"all": {"5": {"metrics": metrics}}}}


def test_partial_pbp_evidence_does_not_require_game6_for_earlier_markets():
    match = {"early_hold_v7": {"ready": False, "p1": _profile(), "p2": _profile()}}
    evidence = build_market_evidence(match)

    assert evidence["legacy_full_ehs_ready"] is False
    assert evidence["market_ready"] is True
    assert evidence["game_state"]["2"]["ready"] is True
    assert evidence["game_state"]["4"]["ready"] is True
    assert evidence["game_state"]["6"]["ready"] is False
    assert evidence["service_holds"]["1"]["ready"] is True
    assert evidence["service_holds"]["2"]["ready"] is True
    assert evidence["service_holds"]["3"]["ready"] is False
    assert evidence["set1_total"]["8.5"]["ready"] is True
    assert evidence["set1_winner"]["ready"] is True
    assert evidence["production_math_changed"] is False
    assert evidence["playable_influence"] is False


def test_market_metric_still_requires_five_matches():
    weak = _profile(after2_11=_metric(4, 75))
    match = {"early_hold_v7": {"ready": False, "p1": weak, "p2": _profile()}}
    evidence = build_market_evidence(match)
    assert evidence["game_state"]["2"]["ready"] is False


def test_enrichment_preserves_legacy_ready_contract():
    match = {"id": 7, "early_hold_v7": {"ready": False, "p1": _profile(), "p2": _profile()}}
    out = enrich_market_evidence(match)
    assert out["early_hold_v7"]["ready"] is False
    assert out["early_hold_v7"]["market_ready"] is True
    assert "game_state@2" in out["early_hold_v7"]["ready_markets"]
