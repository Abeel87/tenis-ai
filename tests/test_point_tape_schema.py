from backend.point_tape_schema import aggregate_schema_audit, inspect_tape_schema, lossless_point_rows


def test_inspection_reports_only_real_fields():
    payload = {
        "meta": {"point_source": "observed"},
        "tape": [
            {"server": 1, "games": [[0], [0]], "points": ["15", "0"], "mystery": "x"},
            {"server": 1, "games": [[0], [0]], "points": ["30", "0"]},
        ],
    }
    report = inspect_tape_schema(payload)
    assert report["rows"] == 2
    assert report["fields"]["server"]["coverage"] == 1.0
    assert report["fields"]["mystery"]["coverage"] == 0.5
    assert "point_winner" not in report["fields"]


def test_lossless_rows_keep_unknown_provider_fields():
    payload = {"tape": [{"server": 2, "games": [[2], [3]], "provider_extra": {"x": 1}}]}
    rows = lossless_point_rows(payload, match_id=123)
    assert rows[0]["match_id"] == 123
    assert rows[0]["server"] == 2
    assert rows[0]["raw"]["provider_extra"] == {"x": 1}


def test_aggregate_coverage_is_match_and_row_based():
    payloads = [
        (1, {"tape": [{"server": 1, "points": ["0", "0"]}, {"server": 1}]}),
        (2, {"tape": [{"server": 2, "games": [[0], [0]]}]}),
    ]
    report = aggregate_schema_audit(payloads)
    assert report["matches"] == 2
    assert report["rows"] == 3
    assert report["fields"]["server"]["row_coverage"] == 1.0
    assert report["fields"]["points"]["rows_present"] == 1
    assert report["fields"]["points"]["matches_present"] == 1
