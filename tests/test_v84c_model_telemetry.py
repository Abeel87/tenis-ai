from datetime import datetime, timezone

from backend.model_telemetry_v84c import build_report


def demo_history():
    return [{
        "match_key": "id:101",
        "status": "settled",
        "scheduled_time": "2026-08-23T10:00:00+00:00",
        "tour": "ATP",
        "surface": "HARD",
        "signals": [
            {"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "score": 72, "result": "hit", "source_model": "adaptive"},
        ],
        "learning_signals_v79b": [
            {"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "score": 75, "result": "hit", "source_model": "early"},
            {"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "score": 73, "result": "hit", "source_model": "serve"},
            {"key": "set1_total|8.5|over", "market": "set1_total", "pick": "over", "score": 74, "result": "hit", "source_model": "consensus"},
        ],
        "autolearn_signals_v84": [{
            "key": "set1_total|8.5|over",
            "market": "set1_total",
            "pick": "over",
            "result": "hit",
            "model_scores": {"current": 71, "catboost": 76, "tabpfn": 74, "ensemble": 74},
            "generator_selected": True,
        }],
    }]


def test_v84c_tracks_specialists_ml_and_generator_without_inventing_roi():
    report = build_report(demo_history(), now=datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc))
    m = report["scopes"]["30d"]["by_model"]
    assert report["version"] == "v8.4C"
    assert m["adaptive"]["accuracy"] == 100.0
    assert m["early"]["accuracy"] == 100.0
    assert m["catboost"]["accuracy"] == 100.0
    assert m["generator"]["selected_n"] == 1
    assert m["generator"]["roi"] is None
    assert "N/D" in m["generator"]["roi_status"]


def test_v84c_segments_and_agreement_are_separate_from_production_weights():
    report = build_report(demo_history(), now=datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc))
    assert report["segments_30d"]["tour"]["ATP"]["early"]["selected_n"] == 1
    assert report["segments_30d"]["surface"]["HARD"]["serve"]["selected_n"] == 1
    assert report["agreement"]["specialists"]["strong_consensus"]["n"] == 1
    assert report["agreement"]["ml"]["strong_consensus"]["n"] == 1
