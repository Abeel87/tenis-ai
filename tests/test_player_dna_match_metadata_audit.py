from backend.player_dna_match_metadata_audit import audit_payloads


def test_metadata_audit_reports_provider_paths_without_joining_features():
    payloads = [
        {
            "match": {
                "startTime": "2026-09-04T10:00:00Z",
                "surface": "Hard",
                "tournament": {"id": 77, "name": "Example Open"},
                "players": {
                    "p1": {"id": 1, "ranking": 12},
                    "p2": {"id": 2, "ranking": 33},
                },
            },
            "meta": {"point_source": "observed"},
            "profiles": [
                {"input_state": {"score": {"timestamp": "2026-09-04T10:01:00Z"}}},
                {"input_state": {"score": {"timestamp": "2026-09-04T10:02:00Z"}}},
            ],
        },
        {
            "match": {
                "startTime": "2026-09-05T11:30:00Z",
                "surface": "Clay",
                "tournament": {"id": 88, "name": "Second Open"},
                "players": {
                    "p1": {"id": 3, "ranking": 21},
                    "p2": {"id": 4, "ranking": None},
                },
            }
        },
    ]

    report = audit_payloads(payloads)
    assert report["gate"] == "AUDIT_ONLY_NO_FEATURE_JOIN"
    assert report["network_calls"] == 0
    assert report["matches"] == 2

    by_path = {row["path"]: row for row in report["all_paths"]}
    assert by_path["match.startTime"]["nonempty_rate"] == 1.0
    assert by_path["match.surface"]["samples"] == ["Hard", "Clay"]
    assert by_path["match.tournament.id"]["types"] == {"int": 2}
    assert by_path["match.players.p1.ranking"]["nonempty"] == 2
    assert by_path["match.players.p2.ranking"]["nonempty"] == 1

    # Two list items in one payload are observations inside one match, not two
    # matches. Presence/non-empty rates therefore stay bounded by 1.0.
    profile_time = by_path["profiles[].input_state.score.timestamp"]
    assert profile_time["present"] == 1
    assert profile_time["nonempty"] == 1
    assert profile_time["present_rate"] == 0.5
    assert profile_time["nonempty_rate"] == 0.5

    likely = {row["path"] for row in report["likely_context_paths"]}
    assert "match.startTime" in likely
    assert "match.surface" in likely
    assert "match.tournament.name" in likely
    assert "match.players.p1.ranking" in likely
