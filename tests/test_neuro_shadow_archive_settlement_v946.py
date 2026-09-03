import json

from backend.neuro_shadow_archive_settlement import settle_from_archive, verified_finals
from backend.neuro_shadow_tracker import register_predictions


def test_verified_finals_accepts_only_explicit_terminal_history_results():
    rows = [
        {
            "match_id": 11,
            "p1": "Alpha",
            "p2": "Beta",
            "status": "settled",
            "result": {
                "status": "completed",
                "winner": "Alpha",
                "sets": [[6, 4], [6, 3]],
                "match_score": "2:0",
                "number_of_sets": 2,
                "total_games": 19,
                "first_set_score": "6:4",
            },
        },
        {"match_id": 12, "p1": "Gamma", "p2": "Delta", "status": "pending", "result": None},
        {"match_id": 13, "p1": "Epsilon", "p2": "Zeta", "result": {"status": "scheduled"}},
    ]
    finals = verified_finals(rows)
    assert len(finals) == 1
    assert finals[0]["match_id"] == 11
    assert finals[0]["p1"] == "Alpha"
    assert finals[0]["p2"] == "Beta"


def test_archive_bridge_recovers_retryable_unverifiable_rows(tmp_path):
    app_history = tmp_path / "history.json"
    neuro_history = tmp_path / "neuro.json"
    stats = tmp_path / "stats.json"

    match = {"id": 21, "p1": "Alpha", "p2": "Beta", "scheduled_time": "2026-09-01T10:00:00Z"}
    shadow = [{
        "market": "set2_total",
        "pick": "over",
        "line": 8.5,
        "probability": 0.72,
        "probability_kind": "shadow_state_probability",
        "mode": "SHADOW",
        "operator_playable": False,
    }]
    rows = register_predictions(match, shadow, created_at="2026-09-01T09:00:00Z")
    rows[0]["settlement"] = "unverifiable"
    neuro_history.write_text(json.dumps(rows), encoding="utf-8")

    app_history.write_text(json.dumps([{
        "match_id": 21,
        "p1": "Alpha",
        "p2": "Beta",
        "status": "settled",
        "result": {
            "status": "completed",
            "winner": "Alpha",
            "sets": [[6, 4], [6, 3]],
            "match_score": "2:0",
            "number_of_sets": 2,
            "total_games": 19,
            "first_set_score": "6:4",
        },
    }]), encoding="utf-8")

    report = settle_from_archive(app_history, neuro_history_path=neuro_history, stats_path=stats)
    settled = json.loads(neuro_history.read_text(encoding="utf-8"))
    assert report["settlement"]["recovered_unverifiable"] == 1
    assert settled[0]["settlement"] == "hit"
    assert settled[0]["target"] == 1.0
