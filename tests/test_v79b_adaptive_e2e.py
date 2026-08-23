from pathlib import Path

from datetime import datetime, timezone

from backend.specialist_learning_v79b import specialist_signals, capture
from backend.adaptive_learning_v79 import collect_training_rows


def sample_match():
    return {
        "id": 7, "model_ready": True, "scheduled_time": "2026-08-24T12:00:00+00:00",
        "p1": "Alpha", "p2": "Beta", "tour": "ATP", "surface": "hard",
        "p1_stats": {
            "matches": 10, "surface_matches": 8, "data_confidence": 80,
            "won": .70, "first_set_won": .70, "second_set_won": .65, "third_set_won": .50,
            "hold_rate": .82, "break_rate": .28, "serve_points_won": .65, "return_points_won": .42,
            "first_set_games": 10.2, "first_set_over85": .82,
        },
        "p2_stats": {
            "matches": 10, "surface_matches": 8, "data_confidence": 80,
            "won": .50, "first_set_won": .50, "second_set_won": .50, "third_set_won": .50,
            "hold_rate": .74, "break_rate": .22, "serve_points_won": .60, "return_points_won": .38,
            "first_set_games": 9.8, "first_set_over85": .75,
        },
        "service_model": {"p1_hold": 82, "p2_hold": 74},
        "match_win": {"Alpha": 70, "Beta": 30},
        "first_set_win": {"Alpha": 68, "Beta": 32},
        "second_set_win": {"Alpha": 65, "Beta": 35},
        "third_set_win": {"Alpha": 60, "Beta": 40},
        "total_sets": {"2": 60, "3": 40},
        "over_under": {
            "8.5": {"over": 82, "under": 18},
            "9.5": {"over": 65, "under": 35},
        },
        "match_over_under": {
            "18.5": {"over": 80, "under": 20},
            "20.5": {"over": 65, "under": 35},
        },
    }


def test_specialist_tracker_connects_all_client_models():
    rows = specialist_signals(sample_match())
    sources = {x["source_model"] for x in rows}
    assert {"early", "serve", "form", "surface", "consensus"} <= sources
    assert all(x["market"] in {"match_winner", "set1_winner", "set1_total", "match_total"} for x in rows)
    assert all(x["learning_only"] is True for x in rows)


def test_capture_freezes_learning_only_signals_on_pending_match():
    match = sample_match()
    hist = [{
        "match_key": "id:7", "match_id": 7, "status": "pending",
        "scheduled_time": match["scheduled_time"], "model_version": "v7.8D-calibration-guard",
        "p1": "Alpha", "p2": "Beta", "tour": "ATP", "surface": "hard",
        "signals": [],
    }]
    got, matches, signals = capture(
        hist, [match], now=datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc)
    )
    assert matches == 1 and signals > 0
    assert got[0]["learning_signals_v79b"]
    assert got[0]["signals"] == []  # official accuracy stays untouched


def test_adaptive_learner_reads_settled_specialist_signals_separately():
    hist = [{
        "model_version": "v7.8D-calibration-guard",
        "tour": "ATP", "surface": "hard",
        "signals": [],
        "learning_signals_v79b": [{
            "market": "set1_total", "line": 8.5, "pick": "over", "score": 76,
            "source_model": "serve", "result": "miss"
        }],
    }]
    rows = collect_training_rows(hist, [])
    assert len(rows) == 1
    assert rows[0]["source_model"] == "serve"
    assert rows[0]["weight"] == 0.85
    assert rows[0]["hit"] == 0.0


ROOT = Path(__file__).resolve().parents[1]


def test_v79b_frontend_is_static_and_visible_before_domcontentloaded():
    idx = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    sw = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")
    ui = (ROOT / "frontend/adaptive-learning-v79.js").read_text(encoding="utf-8")
    assert "Tenis AI v8.0" in idx
    assert 'adaptive-learning-v79.css?v=80' in idx
    assert 'adaptive-learning-v79.js?v=80' in idx
    assert 'data-v79-adaptive="css"' in idx
    assert 'data-v79-adaptive="js"' in idx
    assert "tenis-ai-v80-clean-core" in sw
    assert "p751-detail-screen" in ui
    assert "v79-health" in ui


def test_specialist_signals_are_settled_and_workflow_runs_before_adaptive():
    settle = (ROOT / "backend/live_history_settle.py").read_text(encoding="utf-8")
    flow = (ROOT / ".github/workflows/update-and-pages.yml").read_text(encoding="utf-8")
    assert 'learning_signals_v79b' in settle
    capture_pos = flow.index("Capture specialist learning v7.9B")
    settle_pos = flow.index("Settle history from Live Tennis API")
    adaptive_pos = flow.index("Adaptive Learning v7.9B")
    assert capture_pos < settle_pos < adaptive_pos
