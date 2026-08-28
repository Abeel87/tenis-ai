from __future__ import annotations

from backend.superbet_market_context_v913 import (
    MAX_TOURNAMENT_IDS_PER_REQUEST,
    _tournament_ids,
    batched_request,
)


def test_tournament_id_normalization_dedupes_and_preserves_order():
    assert _tournament_ids("9,1,9, 3 ,") == ["9", "1", "3"]


def test_odds_by_tournaments_is_split_into_max_five_ids(monkeypatch):
    calls = []

    def fake_request(path, api_key, quota, **params):
        calls.append((path, params.get("tournamentIds")))
        ids = str(params.get("tournamentIds") or "").split(",")
        return [{"fixtureId": f"fixture-{x}"} for x in ids if x]

    monkeypatch.setattr("backend.superbet_market_context_v913.time.sleep", lambda _seconds: None)
    quota = {"requests_used_by_v91": 0, "monthly_cap": 150}
    out = batched_request(
        fake_request,
        "odds-by-tournaments",
        "key",
        quota,
        tournamentIds=",".join(str(x) for x in range(1, 13)),
        bookmakers="superbet.pl",
    )

    assert [batch for _path, batch in calls] == [
        "1,2,3,4,5",
        "6,7,8,9,10",
        "11,12",
    ]
    assert all(len(batch.split(",")) <= MAX_TOURNAMENT_IDS_PER_REQUEST for _path, batch in calls)
    assert len(out) == 12


def test_small_tournament_request_stays_single_call():
    calls = []

    def fake_request(path, api_key, quota, **params):
        calls.append(params.get("tournamentIds"))
        return {"fixtureId": "one"}

    result = batched_request(
        fake_request,
        "odds-by-tournaments",
        "key",
        {"requests_used_by_v91": 0, "monthly_cap": 150},
        tournamentIds="1,2,3,4,5",
    )
    assert calls == ["1,2,3,4,5"]
    assert result == {"fixtureId": "one"}
