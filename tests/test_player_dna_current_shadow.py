from datetime import datetime, timezone

from backend.player_dna_current_shadow import (
    _legacy_runtime_validation,
    _profile_map,
    _provider_ranking,
    _serve_feature_row,
)


def _profile(match_id, player_id, opponent_id, matches, serve=0.64, ret=0.38):
    return {
        "target_match_id": match_id,
        "player_id": player_id,
        "opponent_id": opponent_id,
        "strict_as_of": True,
        "current_card_excluded_from_history": True,
        "overall_prior": {
            "matches": matches,
            "serve_win_rate": serve,
            "return_win_rate": ret,
        },
        "same_surface_prior": {
            "matches": max(0, matches - 1),
            "serve_win_rate": serve - 0.01,
            "return_win_rate": ret - 0.01,
        },
    }


def test_current_profile_map_requires_leakage_contract():
    good = _profile("m1", 1, 2, 3)
    bad = _profile("m1", 2, 1, 3)
    bad["current_card_excluded_from_history"] = False
    index = _profile_map([good, bad])
    assert ("m1", 1) in index
    assert ("m1", 2) not in index


def test_serve_features_are_directional_for_server_and_receiver():
    target = {
        "id": 10,
        "surface": "clay",
        "tour": "challenger",
        "best_of": 3,
    }
    server = _profile("10", 1, 2, 5, serve=0.66, ret=0.39)
    receiver = _profile("10", 2, 1, 7, serve=0.62, ret=0.42)
    row = _serve_feature_row(target, server, receiver)
    assert row["surface"] == "clay"
    assert row["tour"] == "CHALLENGER"
    assert row["match_format"] == "BO3"
    assert row["server_overall_serve_rate"] == 0.66
    assert row["receiver_overall_return_rate"] == 0.42
    assert row["server_overall_matches"] == 5
    assert row["receiver_overall_matches"] == 7


def test_current_output_preserves_best_of_for_downstream_simulation():
    from backend.player_dna_current_shadow import _serve_feature_row

    target = {
        "id": 11,
        "surface": "hard",
        "tour": "atp",
        "best_of": 5,
    }
    server = _profile("11", 1, 2, 5)
    receiver = _profile("11", 2, 1, 5)
    features = _serve_feature_row(target, server, receiver)
    assert features["match_format"] == "BO5"


def test_current_runtime_validation_stays_profile_only_when_stateful_signal_is_positive():
    validation = {
        "signal": {
            "status": "STATEFUL_CONTEXT_POSITIVE_HOLDOUT_SIGNAL",
            "legacy_profile_signal_positive": True,
        }
    }
    status, legacy_positive, stateful_status = _legacy_runtime_validation(validation)
    assert status == "POSITIVE_HOLDOUT_SIGNAL"
    assert legacy_positive is True
    assert stateful_status == "STATEFUL_CONTEXT_POSITIVE_HOLDOUT_SIGNAL"


def test_current_runtime_validation_blocks_when_legacy_profile_signal_is_not_positive():
    validation = {
        "signal": {
            "status": "STATEFUL_CONTEXT_POSITIVE_HOLDOUT_SIGNAL",
            "legacy_profile_signal_positive": False,
        }
    }
    status, legacy_positive, stateful_status = _legacy_runtime_validation(validation)
    assert status == "MIXED_OR_NO_INCREMENTAL_SIGNAL"
    assert legacy_positive is False
    assert stateful_status == "STATEFUL_CONTEXT_POSITIVE_HOLDOUT_SIGNAL"


def test_provider_ranking_accepts_only_positive_provider_ints():
    assert _provider_ranking(1) == 1
    assert _provider_ranking(250) == 250
    assert _provider_ranking(0) is None
    assert _provider_ranking(-1) is None
    assert _provider_ranking(True) is None
    assert _provider_ranking("12") is None


def test_current_build_reads_repeatable_points_without_retaining_raw_payloads(tmp_path, monkeypatch):
    import gzip
    import json
    import tracemalloc
    from backend import player_dna_current_shadow as current

    points = tmp_path / "points.gz"
    with gzip.open(points, "wt") as handle:
        for index in range(200):
            handle.write(json.dumps({"match_id": str(index), "unused_raw_payload": "x" * 100_000}) + "\n")
    monkeypatch.setattr(current, "POINTS", points)
    # The old CLI calls this import with its own default path.
    if hasattr(current, "iter_point_rows"):
        monkeypatch.setattr(current, "iter_point_rows", lambda: current._iter_jsonl_gz(points))
    monkeypatch.setattr(current, "PROFILES", tmp_path / "missing-profiles.gz")
    monkeypatch.setattr(current, "RESULTS", tmp_path / "missing-results.json")
    monkeypatch.setattr(current, "OUT", tmp_path / "report.json")

    def consume_twice(source, profiles, results):
        assert sum(1 for _ in source) == 200
        assert sum(1 for _ in source) == 200  # profiles need another pass after features
        return {"status": "TEST_ONLY"}, None

    monkeypatch.setattr(current, "build_current_scores", consume_twice)
    tracemalloc.start()
    try:
        current.build()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 5_000_000  # 20 MB raw payload must not stay resident in the CLI.
