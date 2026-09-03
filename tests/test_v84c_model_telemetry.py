from copy import deepcopy
from datetime import datetime, timezone

from backend.autolearn_v84 import tracking_stats
from backend.model_telemetry_v84c import (
    AUTOLEARN_TRACKER_VERSION,
    build_report,
    collect_rows,
)


def demo_history():
    return [{
        "match_key": "id:101",
        "status": "settled",
        "scheduled_time": "2026-08-23T10:00:00+00:00",
        "autolearn_captured_at": "2026-08-23T08:00:00+00:00",
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
            "tracker_version": AUTOLEARN_TRACKER_VERSION,
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


def test_prod_safe_segments_require_capture_before_match_start():
    history = demo_history()
    missing = deepcopy(history[0])
    missing["match_key"] = "id:missing"
    missing["autolearn_captured_at"] = None
    late = deepcopy(history[0])
    late["match_key"] = "id:late"
    late["autolearn_captured_at"] = "2026-08-23T10:30:00+00:00"
    history.extend([missing, late])

    report = build_report(history, now=datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc))
    # Diagnostics still see all three settled ML predictions.
    assert report["segments_30d"]["tour"]["ATP"]["current"]["selected_n"] == 3
    # PROD-safe telemetry admits only the genuine pre-match snapshot.
    safe = report["prod_safe_segments_30d"]["tour"]["ATP"]
    assert safe["current"]["selected_n"] == 1
    assert safe["catboost"]["selected_n"] == 1
    assert safe["tabpfn"]["selected_n"] == 1
    assert report["prod_safe_rows_30d"] == 3


def test_prod_safe_segments_reject_legacy_or_missing_tracker_regime():
    history = demo_history()
    legacy = deepcopy(history[0])
    legacy["match_key"] = "id:legacy"
    legacy["autolearn_signals_v84"][0]["tracker_version"] = "v8.4A.1"
    missing = deepcopy(history[0])
    missing["match_key"] = "id:no-version"
    missing["autolearn_signals_v84"][0].pop("tracker_version", None)
    history.extend([legacy, missing])

    report = build_report(history, now=datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc))
    # Full diagnostics intentionally retain historical regimes.
    assert report["segments_30d"]["tour"]["ATP"]["current"]["selected_n"] == 3
    # Only the current scoring regime may drive PROD dynamic weights.
    safe = report["prod_safe_segments_30d"]["tour"]["ATP"]
    assert safe["current"]["selected_n"] == 1
    assert safe["catboost"]["selected_n"] == 1
    assert safe["tabpfn"]["selected_n"] == 1
    assert report["prod_safe_rows_30d"] == 3
    assert report["prod_safe_autolearn_tracker_version"] == AUTOLEARN_TRACKER_VERSION


def test_final_is_tracked_separately_without_synthesizing_legacy_final():
    history = demo_history()
    legacy = deepcopy(history[0])
    legacy['match_key'] = 'legacy'
    history[0]['autolearn_signals_v84'][0]['adaptive_prod_v79'] = {'final_score':62}
    history.append(legacy)
    rows = collect_rows(history)
    final = [r for r in rows if r['model']=='adaptive_prod']
    assert len(final) == 1 and final[0]['score'] == 62
    raw = [r for r in rows if r['model']=='ensemble']
    assert len(raw) == 2 and all(r['score']==74 for r in raw)
    track = tracking_stats(history)
    assert track['adaptive_prod']['n'] == 1
    assert track['adaptive_prod']['selected_n'] == 0
    assert track['ensemble']['n'] == 2
