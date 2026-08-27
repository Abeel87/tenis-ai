from backend.symphony_evidence_v90c import augment_match, build_market_catalog
from backend.symphony_engine_v90 import Candidate, _build_outcomes, _joint, _predicate
from backend.symphony_engine_v90c import build_report


def _match():
    return {
        "id": 77,
        "p1": "A",
        "p2": "B",
        "best_of": 3,
        "service_model": {"p1_hold": 78, "p2_hold": 75},
        "game_states": {
            "2": {"2:0": 22, "1:1": 61, "0:2": 17},
            "4": {"4:0": 5, "3:1": 18, "2:2": 52, "1:3": 18, "0:4": 7},
            "6": {"6:0": 1, "5:1": 7, "4:2": 19, "3:3": 44, "2:4": 19, "1:5": 8, "0:6": 2},
        },
        "first_set_win": {"A": 58, "B": 42},
        "second_set_win": {"A": 55, "B": 45},
        "third_set_win": {"A": 57, "B": 43},
        "match_win": {"A": 61, "B": 39},
        "over_under": {
            "8.5": {"over": 78, "under": 22},
            "9.5": {"over": 58, "under": 42},
            "10.5": {"over": 35, "under": 65},
            "11.5": {"over": 18, "under": 82},
            "12.5": {"over": 7, "under": 93},
        },
        "match_over_under": {
            "20.5": {"over": 64, "under": 36},
            "21.5": {"over": 55, "under": 45},
            "22.5": {"over": 47, "under": 53},
        },
        "exact_first_set": {
            "6:3": 18, "6:4": 17, "7:5": 12, "7:6": 11,
            "3:6": 14, "4:6": 13, "5:7": 8, "6:7": 7,
        },
        "exact_match_score": {"2:0": 34, "2:1": 27, "1:2": 22, "0:2": 17},
        "total_sets": {"2 sety": 51, "3 sety": 49},
        "serve_props_v72": {
            "ready": True,
            "p1": {
                "aces": {"lines": {"5.5": {"over": 67, "under": 33}}},
                "double_faults": {"lines": {"2.5": {"over": 43, "under": 57}}},
            },
            "p2": {
                "aces": {"lines": {"3.5": {"over": 62, "under": 38}}},
                "double_faults": {"lines": {"2.5": {"over": 39, "under": 61}}},
            },
        },
        "autolearn_v84": {"signals": []},
    }


def _candidate(key, market, pick, checkpoint=None, line=None):
    return Candidate(
        key=key,
        label=key,
        market=market,
        pick=pick,
        line=line,
        checkpoint=checkpoint,
        prod_score=70,
        shadow_scores={},
        path_probability=None,
        evidence_score=70,
        agreement=0.5,
        conflict=0.0,
    )


def test_catalog_contains_all_major_market_families():
    rows = build_market_catalog(_match())
    markets = {x["market"] for x in rows}
    assert "game_state" in markets
    assert "set1_total" in markets
    assert "match_total" in markets
    assert "match_winner" in markets
    assert "set1_winner" in markets
    assert "set1_exact_score" in markets
    assert "exact_match_score" in markets
    assert "total_sets" in markets
    assert "set1_tiebreak" in markets
    assert "player_aces" in markets
    assert "player_double_faults" in markets


def test_catalog_keeps_reverse_state_two_zero_then_two_two():
    match = _match()
    outcomes = _build_outcomes(match)
    a = _candidate("state|2|2:0", "game_state", "2:0", checkpoint=2)
    b = _candidate("state|4|2:2", "game_state", "2:2", checkpoint=4)
    joint, supported = _joint(outcomes, [_predicate(match, a), _predicate(match, b)])
    assert supported == 2
    assert joint is not None and joint > 0


def test_tiebreak_market_is_derived_from_exact_set_distribution():
    rows = build_market_catalog(_match())
    yes = next(x for x in rows if x["key"] == "set1_tiebreak|yes")
    no = next(x for x in rows if x["key"] == "set1_tiebreak|no")
    assert abs(yes["symphony_raw_probability"] - 18.0) < 1e-9
    assert abs(yes["symphony_raw_probability"] + no["symphony_raw_probability"] - 100.0) < 1e-9


def test_augment_is_read_only_and_adds_missing_markets():
    source = _match()
    augmented, meta = augment_match(source)
    assert source["autolearn_v84"]["signals"] == []
    assert augmented["autolearn_v84"]["signals"]
    assert meta["catalog_size"] > meta["composer_added"] > 0
    assert "set1_exact_score" in meta["families"]


def test_v90c_report_contract(monkeypatch):
    match = _match()

    def fake_read(path, fallback):
        if path.name == "results.json":
            return [match]
        return {}

    monkeypatch.setattr("backend.symphony_engine_v90._read", fake_read)
    report = build_report(legs=4)
    assert report["production_influence"] is False
    assert report["shadow_auto_promotion"] is False
    assert report["contract"]["relative_strength_is_not_probability"] is True
    assert report["matches_count"] == 1
    assert report["matches"][0]["market_adapter"]["catalog_size"] > 0
