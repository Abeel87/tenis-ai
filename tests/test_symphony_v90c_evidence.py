from backend.symphony_evidence_v90c import augment_match, build_market_catalog
from backend.symphony_engine_v90 import Candidate, _build_outcomes, _joint, _predicate
from backend.symphony_engine_v90c import _dedupe_augmented, _extended_predicate, build_report


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
    assert "set2_winner" in markets
    assert "set3_winner" in markets
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


def test_bo3_set2_and_set3_are_exactly_resolvable_from_outcomes():
    match = _match()
    outcomes = _build_outcomes(match)
    pred = _extended_predicate(_predicate)

    s2a = _candidate("set2|A", "set2_winner", "A")
    s2b = _candidate("set2|B", "set2_winner", "B")
    p2a, n2a = _joint(outcomes, [pred(match, s2a)])
    p2b, n2b = _joint(outcomes, [pred(match, s2b)])
    assert n2a == n2b == 1
    assert abs((p2a + p2b) - 1.0) < 1e-9

    s3a = _candidate("set3|A", "set3_winner", "A")
    s3b = _candidate("set3|B", "set3_winner", "B")
    p3a, n3a = _joint(outcomes, [pred(match, s3a)])
    p3b, n3b = _joint(outcomes, [pred(match, s3b)])
    assert n3a == n3b == 1
    three_set_mass = sum(o["prob"] for o in outcomes if o["set_count"] == 3)
    assert abs((p3a + p3b) - three_set_mass) < 1e-9


def test_augment_is_read_only_and_adds_missing_markets():
    source = _match()
    augmented, meta = augment_match(source)
    assert source["autolearn_v84"]["signals"] == []
    assert augmented["autolearn_v84"]["signals"]
    assert meta["catalog_size"] > meta["composer_added"] > 0
    assert "set1_exact_score" in meta["families"]


def test_semantic_alias_dedupe_prefers_existing_prod_rows():
    source = _match()
    source["autolearn_v84"]["signals"] = [
        {"key": "match_win|A", "market": "match_win", "pick": "A", "ensemble": 81},
        {"key": "state2|1:1", "market": "state2", "pick": "1:1", "ensemble": 79},
    ]
    augmented, meta = augment_match(source)
    before = len(augmented["autolearn_v84"]["signals"])
    augmented, meta = _dedupe_augmented(augmented, meta)
    rows = augmented["autolearn_v84"]["signals"]
    after = len(rows)

    match_a = [x for x in rows if x.get("pick") == "A" and x.get("market") in {"match_win", "match_winner"}]
    state_11 = [x for x in rows if x.get("pick") == "1:1" and (x.get("checkpoint") == 2 or "state2" in str(x.get("key")))]

    assert len(match_a) == 1
    assert match_a[0]["market"] == "match_win"
    assert len(state_11) == 1
    assert state_11[0]["market"] == "state2"
    assert after < before
    assert meta["alias_duplicates_removed"] >= 2


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
    assert report["contract"]["semantic_alias_dedupe"] is True
    assert report["contract"]["bo3_set2_set3_exact_joint"] is True
    assert report["matches_count"] == 1
    assert report["matches"][0]["market_adapter"]["catalog_size"] > 0
