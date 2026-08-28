from backend.symphony_evidence_v90c import augment_match, build_market_catalog, composer_catalog


def _match():
    return {
        "id": 991,
        "p1": "A",
        "p2": "B",
        "serve_props_v72": {
            "ready": True,
            "p1": {
                "aces": {"lines": {"1.5": {"over": 88, "under": 12}}},
                "double_faults": {"lines": {"0.5": {"over": 91, "under": 9}}},
            },
            "p2": {
                "aces": {"lines": {"2.5": {"over": 67, "under": 33}}},
                "double_faults": {"lines": {"1.5": {"over": 63, "under": 37}}},
            },
        },
        "autolearn_v84": {"signals": []},
    }


def test_model_generated_serve_lines_stay_in_analysis_catalog_but_not_composer():
    catalog = build_market_catalog(_match())
    serve = [x for x in catalog if x.get("market") in {"player_aces", "player_double_faults"}]
    assert serve
    assert all(x.get("operator") == "superbet" for x in serve)
    assert all(x.get("operator_line_verified") is False for x in serve)
    assert all(x.get("symphony_actionable") is False for x in serve)
    assert all(x.get("operator_line_source") == "model_generated_not_bookmaker" for x in serve)

    composer = composer_catalog(catalog)
    assert not [x for x in composer if x.get("market") in {"player_aces", "player_double_faults"}]


def test_augment_does_not_leak_unverified_numeric_serve_props_into_symphony():
    match = _match()
    match["autolearn_v84"]["signals"] = [
        {
            "key": "player_aces|p1|1.5|over",
            "market": "player_aces",
            "pick": "over",
            "line": 1.5,
            "ensemble": 92,
        },
        {
            "key": "match_win|A",
            "market": "match_win",
            "pick": "A",
            "ensemble": 70,
        },
    ]

    augmented, meta = augment_match(match)
    rows = augmented["autolearn_v84"]["signals"]
    assert not [x for x in rows if x.get("market") == "player_aces"]
    assert [x for x in rows if x.get("market") == "match_win"]
    assert meta["operator"] == "superbet"
    assert meta["operator_line_guard"] is True
    assert meta["serve_prop_lines_analysis_only"] is True
    assert meta["unverified_operator_lines"] > 0
    assert meta["suppressed_existing_unverified_lines"] == 1


def test_future_verified_bookmaker_serve_line_can_become_actionable():
    verified = {
        "key": "player_aces|p1|4.5|over",
        "market": "player_aces",
        "pick": "over",
        "line": 4.5,
        "score": 73,
        "symphony_raw_probability": 73,
        "operator": "superbet",
        "operator_line_verified": True,
    }
    composer = composer_catalog([verified])
    assert composer == [verified]
