from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from backend import readiness_engine_shadow as readiness


def _player_state(
    *,
    player_id: int,
    surface: str = "Hard",
    current_matches: int = 10,
    surface_matches: int = 5,
    rank: int | None = 100,
    opponent_matches: int = 6,
) -> dict:
    has_current = current_matches > 0
    return {
        "player_id": player_id,
        "target_surface": surface,
        "current_season": {
            "matches": current_matches,
            "serve_win_rate": 0.62 if has_current else None,
            "return_win_rate": 0.38 if has_current else None,
        },
        "current_surface_state": {
            "current_season": {"matches": surface_matches},
        },
        "ranking_momentum": {"effective_rank": rank},
        "opponent_adjusted_performance_trend": {
            "support": {"all_prior_matches": opponent_matches},
        },
    }


def _state_report(
    *,
    match_id: str = "1",
    legacy_model_ready: bool = True,
    p1: dict | None = None,
    p2: dict | None = None,
) -> dict:
    return {
        "current_card": {
            "matches": [
                {
                    "match_id": match_id,
                    "current_engine_reference": {
                        "selected_existing_fields": {
                            "model_ready": legacy_model_ready,
                        }
                    },
                    "player_state": {
                        "p1": p1 or _player_state(player_id=11),
                        "p2": p2 or _player_state(player_id=22, rank=120),
                    },
                }
            ]
        }
    }
def _pbp_evidence(*ready_markets: str) -> dict:
    return {
        "mode": "EVIDENCE_ONLY",
        "min_matches_per_metric": 5,
        "ready_markets": list(ready_markets),
        "game_state": {
            "2": {"sample_floor": 5 if "game_state@2" in ready_markets else 3},
            "4": {"sample_floor": 3},
            "6": {"sample_floor": 2},
        },
        "balanced_sequence": {"sample_floor": 2},
        "set1_total": {
            "8.5": {"sample_floor": 3},
            "9.5": {"sample_floor": 2},
        },
        "set1_winner": {
            "sample_floor": 5 if "set1_winner" in ready_markets else 3,
        },
        "service_holds": {
            "1": {"p1": {"n": 5}, "p2": {"n": 5}},
            "2": {"p1": {"n": 3}, "p2": {"n": 5}},
            "3": {"p1": {"n": 2}, "p2": {"n": 5}},
        },
    }


def _result(*, model_ready: bool = True, pbp: dict | None = None) -> dict:
    early = {"market_evidence_v940": pbp} if pbp is not None else {}
    return {
        "id": 1,
        "scheduled_time": "2026-09-19T10:00:00+00:00",
        "p1": "Alpha",
        "p2": "Beta",
        "model_ready": model_ready,
        "early_hold_v7": early,
    }
def _history(*rows: dict, visible: int = 1, results: list[dict] | None = None) -> dict:
    snapshot_results = results or [_result(pbp=_pbp_evidence("game_state@2"))]
    return {
        "summary": {"visible_matches": visible},
        "source_snapshot": {
            "results_snapshot_contract": readiness.SNAPSHOT_CONTRACT,
            "results_snapshot_sha256": readiness.results_snapshot_sha256(snapshot_results),
        },
        "matches": list(rows),
    }


def _compose(
    result: dict | None = None,
    history: dict | None = None,
    player_state: dict | None = None,
) -> dict:
    current_result = result or _result(pbp=_pbp_evidence("game_state@2"))
    current_history = history if history is not None else _history(results=[current_result])
    return readiness.compose_readiness(
        [current_result],
        current_history,
        player_state or _state_report(),
        source_reports={
            "profile": {"version": "profile", "gate": "AUDIT_ONLY"},
            "service_source": {"version": "service", "mode": "SHADOW"},
            "pbp_split": {"version": "pbp", "mode": "SHADOW"},
        },
        generated_at="2026-09-19T00:00:00+00:00",
    )


def test_tri_state_semantics_do_not_promote_coverage_to_ready():
    report = _compose()
    row = report["matches"][0]
    dims = row["dimensions"]

    assert dims["identity"]["status"] == readiness.READY
    assert dims["freshness"]["status"] == readiness.UNKNOWN
    assert dims["current_season"]["status"] == readiness.UNKNOWN
    assert dims["surface"]["status"] == readiness.UNKNOWN
    assert dims["rank_context"]["status"] == readiness.READY
    assert dims["serve_return"]["status"] == readiness.UNKNOWN
    assert dims["pbp"]["status"] == readiness.READY
    assert dims["opponent_context"]["status"] == readiness.UNKNOWN
def test_identity_is_fail_closed_without_safe_resolution():
    history_row = {
        "id": 1,
        "players": [
            {
                "player": "Alpha",
                "matches": 0,
                "current_identity_mode": "none",
                "current_history_player_key": None,
                "reason": "no_safe_identity_candidate",
            },
            {
                "player": "Beta",
                "matches": 2,
                "current_identity_mode": "exact",
                "current_history_player_key": "beta",
                "reason": "insufficient_pre_match_sample",
            },
        ],
    }
    report = _compose(history=_history(history_row))
    identity = report["matches"][0]["dimensions"]["identity"]
    assert identity["status"] == readiness.NOT_READY
    assert "IDENTITY_NO_SAFE_IDENTITY_CANDIDATE" in identity["reason_codes"]


def test_history_snapshot_mismatch_stays_unknown():
    report = _compose(history=_history(visible=999))
    identity = report["matches"][0]["dimensions"]["identity"]
    assert identity["status"] == readiness.UNKNOWN
    assert identity["reason_codes"] == ["IDENTITY_AUDIT_SNAPSHOT_MISMATCH_OR_MISSING"]
def test_missing_current_surface_rank_and_opponent_evidence_are_not_ready():
    p1 = _player_state(
        player_id=11,
        surface="unknown",
        current_matches=0,
        surface_matches=0,
        rank=None,
        opponent_matches=0,
    )
    p2 = _player_state(player_id=22, surface="unknown")
    report = _compose(player_state=_state_report(p1=p1, p2=p2))
    dims = report["matches"][0]["dimensions"]

    assert dims["current_season"]["status"] == readiness.NOT_READY
    assert dims["surface"]["status"] == readiness.NOT_READY
    assert dims["rank_context"]["status"] == readiness.NOT_READY
    assert dims["serve_return"]["status"] == readiness.NOT_READY
    assert dims["opponent_context"]["status"] == readiness.NOT_READY


def test_pbp_market_readiness_reuses_existing_market_contract():
    result = _result(pbp=_pbp_evidence("game_state@2", "set1_winner", "service_hold_1"))
    report = _compose(result=result)
    markets = report["matches"][0]["market_readiness"]["pbp_early_hold"]["markets"]

    assert markets["game_state@2"]["status"] == readiness.READY
    assert markets["set1_winner"]["status"] == readiness.READY
    assert markets["service_hold_1"]["status"] == readiness.READY
    assert markets["game_state@4"]["status"] == readiness.NOT_READY
    assert markets["game_state@2"]["support"]["min_matches_per_metric"] == 5
def test_missing_pbp_evidence_is_unknown_not_false_not_ready():
    report = _compose(result=_result(pbp=None))
    row = report["matches"][0]
    assert row["dimensions"]["pbp"]["status"] == readiness.UNKNOWN
    markets = row["market_readiness"]["pbp_early_hold"]["markets"]
    assert {payload["status"] for payload in markets.values()} == {readiness.UNKNOWN}


def test_legacy_model_ready_is_observational_and_input_is_not_mutated():
    result = _result(model_ready=True, pbp=_pbp_evidence("game_state@2"))
    before = deepcopy(result)
    report = _compose(result=result)

    assert result == before
    row = report["matches"][0]
    assert row["legacy_model_ready"] is True
    assert row["legacy_model_ready_unchanged"] is True
    assert row["market_readiness"]["current_engine_generic"]["status"] == readiness.UNKNOWN
    assert report["semantic_contract"]["no_single_overall_ready_boolean"] is True
    assert "overall_ready" not in row


def test_current_engine_reference_mismatch_blocks_evidence_status():
    report = _compose(
        result=_result(model_ready=True, pbp=_pbp_evidence("game_state@2")),
        player_state=_state_report(legacy_model_ready=False),
    )
    assert report["status"] == "READINESS_SEMANTICS_SOURCE_MISMATCH"
    assert report["source_snapshot"]["legacy_model_ready_reference_mismatches"] == 1
def test_reason_codes_are_deterministic_and_safety_is_hard_closed():
    report = _compose()
    for row in report["matches"]:
        for payload in row["dimensions"].values():
            assert payload["reason_codes"] == sorted(set(payload["reason_codes"]))

    for key in (
        "production_influence",
        "runtime_scoring_enabled",
        "runtime_gating_enabled",
        "training_join_enabled",
        "current_engine_write_enabled",
        "legacy_model_ready_write_enabled",
        "probability_created",
        "weights_created",
        "thresholds_created",
        "feature_activation",
        "symphony2_influence",
        "superbet_playable_influence",
        "ineed_influence",
        "auto_promote",
        "promotion_gate",
    ):
        assert report[key] is False
    assert report["network_calls"] == 0


def test_workflow_wires_readiness_engine_into_existing_point_tape_artifact():
    workflow = Path(".github/workflows/point-tape-audit.yml").read_text(encoding="utf-8")
    history_refresh = workflow.index("python backend/history_coverage_audit.py")
    history_stamp = workflow.index("python backend/snapshot_digest.py stamp-report")
    readiness_build = workflow.index("python backend/readiness_engine_shadow.py")
    assert history_refresh < history_stamp < readiness_build
    assert "frontend/data/readiness_engine_shadow.json" in workflow
    assert "tests/test_readiness_engine_shadow.py" in workflow


def test_history_exception_ids_must_belong_to_current_results_snapshot():
    stale_row = {
        "id": 999,
        "players": [
            {"current_identity_mode": "exact", "current_history_player_key": "a", "reason": "sufficient_history"},
            {"current_identity_mode": "exact", "current_history_player_key": "b", "reason": "sufficient_history"},
        ],
    }
    report = _compose(history=_history(stale_row, visible=1))
    assert report["status"] == "READINESS_SEMANTICS_SOURCE_MISMATCH"
    assert report["source_snapshot"]["history_coverage_snapshot_aligned"] is False
    assert report["matches"][0]["dimensions"]["identity"]["status"] == readiness.UNKNOWN


def test_history_same_count_and_ids_but_wrong_results_digest_is_rejected():
    current = _result(model_ready=True, pbp=_pbp_evidence("game_state@2"))
    stale = deepcopy(current)
    stale["model_ready"] = False
    report = _compose(result=current, history=_history(visible=1, results=[stale]))
    assert report["status"] == "READINESS_SEMANTICS_SOURCE_MISMATCH"
    assert report["source_snapshot"]["history_coverage_snapshot_aligned"] is False
    assert report["matches"][0]["dimensions"]["identity"]["status"] == readiness.UNKNOWN


def test_player_state_match_ids_must_exactly_match_current_results_snapshot():
    report = _compose(player_state=_state_report(match_id="999"))
    assert report["status"] == "READINESS_SEMANTICS_SOURCE_MISMATCH"
    assert report["source_snapshot"]["player_state_snapshot_aligned"] is False
