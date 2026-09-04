from backend.player_dna_context_time_audit import audit_payloads


def _payload(*, scheduled="2026-09-04T10:00:00Z", times=None):
    times = times or [
        "2026-09-04T10:00:10Z",
        "2026-09-04T10:00:20Z",
        "2026-09-04T10:00:30Z",
    ]
    return {
        "match": {
            "id": 123,
            "scheduled_time": scheduled,
            "surface": "Hard",
            "tour": "atp",
            "format": "bo3",
            "round_code": "qf",
            "indoor": False,
            "is_qualifying": False,
            "players": {
                "p1": {"id": 11, "ranking": 25},
                "p2": {"id": 22, "ranking": 40},
            },
        },
        "tape": [
            {"sets": [0, 0], "games": [0, 0], "points": ["0", "0"], "server": 1, "timestamp": times[0]},
            {"sets": [0, 0], "games": [0, 0], "points": ["15", "0"], "server": 1, "point_winner": 1, "timestamp": times[1]},
            {"sets": [0, 0], "games": [0, 0], "points": ["30", "0"], "server": 1, "point_winner": 1, "timestamp": times[2]},
        ],
        "meta": {"point_source": "observed"},
    }


def test_audit_reports_context_distribution_and_clean_chronology():
    report = audit_payloads([("m1", _payload())])
    assert report["gate"] == "AUDIT_ONLY_NO_PROFILE_AGGREGATION"
    assert report["network_calls"] == 0
    assert report["shadow_only"] is True
    assert report["training_join_enabled"] is False
    assert report["profile_aggregation_enabled"] is False
    assert report["matches"] == 1
    assert report["valid_context_matches"] == 1
    assert report["context_coverage"] == 1.0
    assert report["distributions"]["surface"] == {"hard": 1}
    assert report["distributions"]["tour"] == {"ATP": 1}
    assert report["ranking_coverage"]["both_rate"] == 1.0
    timing = report["time_ordering"]
    assert timing["events_total"] == 2
    assert timing["parseable_event_times"] == 2
    assert timing["invalid_event_times"] == 0
    assert timing["matches_with_non_monotonic_events"] == 0
    assert timing["events_before_scheduled"] == 0
    assert timing["chronology_clean_candidate"] is True


def test_audit_detects_time_ordering_problems_without_enabling_training():
    payload = _payload(times=[
        "2026-09-04T09:59:40Z",
        "2026-09-04T10:00:20Z",
        "2026-09-04T09:59:50Z",
    ])
    report = audit_payloads([("m1", payload)])
    timing = report["time_ordering"]
    assert timing["matches_with_non_monotonic_events"] == 1
    assert timing["events_before_scheduled"] == 1
    assert timing["chronology_clean_candidate"] is False
    assert report["training_join_enabled"] is False
    assert report["profile_aggregation_enabled"] is False


def test_invalid_match_context_is_counted_and_never_profile_ready():
    payload = _payload()
    payload["match"]["players"]["p1"]["id"] = "11"
    report = audit_payloads([("m1", payload)])
    assert report["matches"] == 1
    assert report["valid_context_matches"] == 0
    assert report["rejected_context_matches"] == 1
    assert report["context_coverage"] == 0.0
    assert report["time_ordering"]["chronology_clean_candidate"] is False
