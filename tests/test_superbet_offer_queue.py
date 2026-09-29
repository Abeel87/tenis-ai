"""Regression for exact-offer queues larger than the former 24-request slice."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


def _refresh(*, total_used=0, direct_used=0, previous=None):
    # Isolate the core from adapter monkeypatches installed by other test modules.
    spec = importlib.util.spec_from_file_location(
        "offer_queue_core", Path(__file__).resolve().parents[1] / "backend/superbet_market_core.py"
    )
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    now = datetime(2026, 9, 29, 3, tzinfo=timezone.utc)
    start = (now + timedelta(hours=3)).isoformat()
    fixtures = [
        {"fixtureId": f"fixture-{i}", "participant1Name": f"Alpha {i}",
         "participant2Name": f"Beta {i}", "startTime": start, "tournamentId": "one"}
        for i in range(48)
    ]
    results = [
        {"id": i, "p1": row["participant1Name"], "p2": row["participant2Name"],
         "scheduled_time": start} for i, row in enumerate(fixtures)
    ]
    meta = {"1": {"marketName": "Winner", "outcomes": {
        "1": {"outcomeName": "1"}, "2": {"outcomeName": "2"}}}}
    previous = previous or {
        "generated_at": (now - timedelta(hours=2)).isoformat(),
        "market_meta_generated_at": now.isoformat(), "market_meta_cache": meta,
        "quota_guard": {"month": "2026-09", "requests_used_by_v91": total_used,
                        "direct_fixture_requests_used": direct_used}
    }
    requested = []
    def request(path, api_key, quota, **params):
        quota["requests_used_by_v91"] += 1
        if path == "fixtures":
            return fixtures
        if path == "odds-by-tournaments":
            return []
        assert path == "odds"
        assert params["bookmakers"] == "superbet.pl"
        fid = params["fixtureId"]
        requested.append(fid)
        row = next(row for row in fixtures if row["fixtureId"] == fid)
        return [{**row, "bookmakerOdds": {"superbet.pl": {
            "bookmakerIsActive": True, "suspended": False,
            "markets": {"1": {"marketActive": True, "outcomes": {
                str(i): {"players": {str(i): {"active": True,
                    "bookmakerOutcomeId": str(i)}}} for i in (1, 2)
            }}}
        }}}]
    with patch.dict(core.os.environ, {"ODDSPAPI_API_KEY": "test"}), \
         patch.object(core, "_read", return_value=previous), \
         patch.object(core, "_write"), patch.object(core, "_request", side_effect=request), \
         patch.object(core, "_availability_due", return_value=True), \
         patch.object(core.time, "sleep"):
        report = core.refresh_availability(results, now=now)
    assert report["refresh_status"] == "OK", report
    return report, requested


def test_all_due_exact_offers_are_checked_without_per_refresh_truncation():
    report, requested = _refresh()
    assert report["direct_fixture_requests_due"] == 48
    assert len(requested) == len(set(requested)) == 48
    assert report["direct_fixture_skipped_budget"] == 0
    assert len(report["fixtures"]) == 48
    assert all(row["bookmaker"] == "superbet.pl" for row in report["fixtures"])
    assert all(row["operator_offer_source"] == "odds_by_fixture" for row in report["fixtures"])


def test_completed_milestone_is_not_requested_again():
    first, _ = _refresh()
    second, requested = _refresh(previous=first)
    assert requested == []
    assert second["direct_fixture_requests_due"] == 0
    assert len(second["fixtures"]) == 48


def test_monthly_account_budget_still_bounds_queue():
    report, requested = _refresh(total_used=3995)
    assert len(requested) == 3  # Discovery and tournament request use two slots.
    assert report["quota_guard"]["requests_used_by_v91"] == 4000
    assert report["direct_fixture_skipped_budget"] == 45


def test_monthly_direct_budget_still_bounds_queue():
    report, requested = _refresh(direct_used=1697)
    assert len(requested) == 3
    assert report["quota_guard"]["direct_fixture_requests_used"] == 1700
    assert report["direct_fixture_skipped_budget"] == 45
