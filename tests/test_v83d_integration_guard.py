from datetime import datetime, timezone
from pathlib import Path

from backend.scenario_settlement_v83c import build_feed

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_v83d_manual_builder_resolves_full_total_ladder():
    s = read("frontend/scenario-studio-v82a.js")
    assert "s=m&&scenarioSignals(m).find(x=>x.key===sk)" in s


def test_v83d_keeps_v82a6_pin_and_busts_only_settlement_asset():
    h = read("frontend/index.html")
    assert 'scenario-studio-v82a.js?v=82a6' in h
    assert 'scenario-settlement-v83c.js?v=83d1' in h
    assert h.count("scenario-studio-v82a.js") == 1
    assert h.count("scenario-settlement-v83c.js") == 1


def test_v83d_idless_settled_match_is_exported():
    history = [{
        "match_id": None,
        "match_key": "a|b|2026-08-23|test",
        "scheduled_time": "2026-08-23T18:00:00Z",
        "p1": "A",
        "p2": "B",
        "tournament": "Test",
        "status": "settled",
        "result": {
            "status": "completed",
            "winner": "A",
            "sets": [[6, 4], [6, 3]],
            "match_score": "2:0",
            "number_of_sets": 2,
            "total_games": 19,
            "first_set_score": "6:4",
        },
    }]
    feed = build_feed(history, [], now=datetime(2026, 8, 23, 21, 0, tzinfo=timezone.utc))
    assert feed["version"] == "v8.3D"
    assert feed["count"] == 1
    assert feed["matches"][0]["match_key"] == "a|b|2026-08-23|test"


def test_v83d_settlement_has_recheck_and_pbp_grace():
    s = read("frontend/scenario-settlement-v83c.js")
    assert "const VERSION='v8.3D'" in s
    assert "PBP_GRACE_HOURS=36" in s
    assert "function terminalResult(item)" in s
    assert "function pbpUnavailable(item,outcome,reason)" in s
    assert "market==='game_state'" in s
    assert "push na linii" in s


def test_v83d_workflow_order_and_guard():
    w = read(".github/workflows/update-and-pages.yml")
    markers = [
        "Central API Quota Guard v8.3B",
        "Update analysis",
        "Enrich Early Hold from BASIC point-by-point",
        "Track + backtest PBP",
        "Settle history from Live Tennis API",
        "Build Scenario Settlement feed v8.3C",
        "Historical backfill v8.3B (central spare quota)",
        "Adaptive Learning v7.9B",
        "Final API quota report v8.3B",
        "Integration Guard v8.3D",
    ]
    pos = [w.index(x) for x in markers]
    assert pos == sorted(pos)
    assert w.count("Integration Guard v8.3D") == 1


def test_v83d2_history_backfill_imports_work_as_package_and_script():
    s = read("backend/history_backfill_v83.py")
    assert "from .api_quota_v83b import quota_budget, record_calls" in s
    assert "from api_quota_v83b import quota_budget, record_calls" in s
    assert "from .pbp_tracker import backtest_cache" in s
    assert "from pbp_tracker import backtest_cache" in s
