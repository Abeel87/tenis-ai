from backend import superbet_fixture_matching as matching

def test_time_rejection_evidence_survives_full_unmatched_sample():
    matching.reset_telemetry()
    for i in range(matching.MAX_SAMPLE_ROWS):
        matching.best_fixture_for_match({"p1": f"Missing Player {i}", "p2": "Other Person", "scheduled_time": "2026-09-28T12:00:00Z"}, [])
    match = {"id": 42, "p1": "Alice Smith", "p2": "Beth Jones", "scheduled_time": "2026-09-28T12:00:00Z"}
    fixture = {"fixtureId": "provider-7", "participant1Name": "Alice Smith", "participant2Name": "Beth Jones", "startTime": "2026-09-29T12:00:00Z"}
    assert matching.best_fixture_for_match(match, [fixture]) is None
    live = matching.report()["live"]
    assert len(live["unmatched_samples"]) == matching.MAX_SAMPLE_ROWS
    sample = live["samples_by_reason"]["TIME_GUARD"][0]
    assert sample["match_id"] == 42
    assert sample["candidates"][0]["fixture_id"] == "provider-7"
    assert sample["candidates"][0]["start_time"] == fixture["startTime"]
    assert sample["candidates"][0]["delta_hours"] == 24
    assert sample["candidates"][0]["exact_pair"] is True

def test_diagnostics_preserve_valid_matching_and_are_bounded():
    matching.reset_telemetry()
    match = {"p1": "Alice Smith", "p2": "Beth Jones", "scheduled_time": "2026-09-28T12:00:00Z"}
    fixture = {"fixtureId": "provider-7", "participant1Name": "Alice Smith", "participant2Name": "Beth Jones", "startTime": "2026-09-28T12:00:00Z"}
    assert matching.best_fixture_for_match(match, [fixture]) is fixture
    assert matching.report()["live"]["samples_by_reason"] == {}
    fixture["startTime"] = "2026-09-29T12:00:00Z"
    for _ in range(20):
        assert matching.best_fixture_for_match(match, [fixture]) is None
    assert len(matching.report()["live"]["samples_by_reason"]["TIME_GUARD"]) == matching.MAX_SAMPLE_ROWS
