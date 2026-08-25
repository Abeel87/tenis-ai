from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def module():
    spec = importlib.util.spec_from_file_location("mt84c", ROOT / "backend/model_telemetry_v84c.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rows(pattern, score=75):
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    out = []
    for i, target in enumerate(pattern):
        out.append({
            "scheduled_time": (now - timedelta(minutes=(len(pattern) - i) * 5)).isoformat(),
            "score": score,
            "target": int(target),
            "model": "current",
            "match_key": f"id:{i}",
            "candidate_key": f"k:{i}",
            "market": "set1_total",
            "tour": "ATP",
            "surface": "HARD",
            "odds": None,
            "checkpoint": None,
        })
    return out


def test_trend_rising_and_falling():
    m = module()
    t = m.trend_summary(rows(([1] * 10 + [0] * 10) + ([1] * 18 + [0] * 2)), model="current")
    assert t["status"] == "rising"
    assert t["accuracy_delta_pp"] > 0
    assert t["brier_delta"] < 0
    t = m.trend_summary(rows(([1] * 18 + [0] * 2) + ([1] * 10 + [0] * 10)), model="current")
    assert t["status"] == "falling"
    assert t["accuracy_delta_pp"] < 0
    assert t["brier_delta"] > 0


def test_small_sample_is_collecting():
    m = module()
    t = m.trend_summary(rows([1, 1, 0, 1, 0, 1, 1]), model="current")
    assert t["status"] == "collecting"
    assert t["selected_n"] == 7


def test_game_state_progress_counts_pbp_results():
    m = module()
    history = [
        {
            "match_key": "id:1",
            "scheduled_time": "2026-08-24T10:00:00+00:00",
            "status": "settled",
            "game_state_learning_v84e1": [
                {"market": "game_state", "checkpoint": 2, "pick": "1:1", "score": 72, "result": "hit"},
                {"market": "game_state", "checkpoint": 4, "pick": "2:2", "score": 70, "result": "miss"},
                {"market": "game_state", "checkpoint": 6, "pick": "3:3", "score": 68, "result": "unverifiable"},
            ],
        },
        {
            "match_key": "id:2",
            "scheduled_time": "2026-08-24T11:00:00+00:00",
            "status": "pending",
            "game_state_learning_v84e1": [
                {"market": "game_state", "checkpoint": 2, "pick": "1:1", "score": 74, "result": "pending"},
                {"market": "game_state", "checkpoint": 4, "pick": "2:2", "score": 71, "result": "pending"},
                {"market": "game_state", "checkpoint": 6, "pick": "3:3", "score": 69, "result": "pending"},
            ],
        },
    ]
    g = m.game_state_progress(history)
    assert g["checkpoints"]["2"]["tracked"] == 2
    assert g["checkpoints"]["2"]["settled"] == 1
    assert g["checkpoints"]["2"]["hits"] == 1
    assert g["checkpoints"]["4"]["misses"] == 1
    assert g["checkpoints"]["6"]["waiting_pbp"] == 2


def test_report_exports_e2_sections():
    m = module()
    r = m.build_report([], now=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
    assert r["trends_v84e2"]["version"] == "v8.4E2"
    assert set(r["game_state_progress_v84e2"]["checkpoints"]) == {"2", "4", "6"}
    assert "quality_lock_v852" in r["trends_v84e2"]


def test_quality_lock_v852_capture_time_split():
    m = module()
    # Scheduled time is constant (early), proving split uses autolearn_captured_at, NOT scheduled_time
    test_rows = [
        # Before cutover (2026-08-25T09:55:27Z)
        {
            "model": "current",
            "score": 75,
            "target": 1,
            "scheduled_time": "2026-08-01T10:00:00Z",
            "autolearn_captured_at": "2026-08-25T09:00:00Z",
        },
        # At cutover
        {
            "model": "current",
            "score": 75,
            "target": 0,
            "scheduled_time": "2026-08-01T10:00:00Z",
            "autolearn_captured_at": "2026-08-25T09:55:27Z",
        },
        # After cutover
        {
            "model": "current",
            "score": 75,
            "target": 1,
            "scheduled_time": "2026-08-01T10:00:00Z",
            "autolearn_captured_at": "2026-08-25T10:00:00Z",
        },
        # Missing capture time (must be counted as unknown, NEVER before_v852)
        {
            "model": "current",
            "score": 75,
            "target": 1,
            "scheduled_time": "2026-08-01T10:00:00Z",
            "autolearn_captured_at": None,
        },
    ]

    ql = m.build_quality_lock_v852(test_rows)
    curr = ql["current"]

    # Sections contain selected_n, accuracy, brier
    assert set(curr["before_v852"].keys()) == {"selected_n", "accuracy", "brier"}
    assert set(curr["since_v852"].keys()) == {"selected_n", "accuracy", "brier"}

    # before cutover -> before_v852
    assert curr["before_v852"]["selected_n"] == 1
    assert curr["before_v852"]["accuracy"] == 100.0

    # at/after cutover -> since_v852
    assert curr["since_v852"]["selected_n"] == 2
    assert curr["since_v852"]["accuracy"] == 50.0

    # missing capture time -> unknown_capture_time_n (never before_v852)
    assert curr["unknown_capture_time_n"] == 1


def test_frontend_is_additive_and_no_new_polling():
    js = (ROOT / "frontend/model-trends-v84e2.js").read_text(encoding="utf-8")
    idx = (ROOT / "frontend/index.html").read_text(encoding="utf-8")

    assert "fetch(" not in js
    assert "new MutationObserver(" not in js
    assert "setInterval(" not in js
    assert "historyRows" not in js

    assert "Ensemble selector proxy" in js
    assert "zbieramy próbę" in js
    assert "model-trends-v84e2.js?v=84e2&hf=852a1" in idx
    assert "autolearn-v84.js?v=84a1&hf=84b1" in idx
    assert "scenario-studio-v82a.js?v=82a6&hf=84a1" in idx
