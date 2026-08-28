from __future__ import annotations

import math
from pathlib import Path

from backend import symphony_bo5_compact_v93c as compact
from backend import symphony_engine_v90 as core
from backend import symphony_scenario_lattice_v93 as deep
from backend import symphony_scenario_runtime_v93 as runtime

ROOT = Path(__file__).resolve().parents[1]


def _match():
    return {
        "id": 9351,
        "p1": "Alpha",
        "p2": "Beta",
        "best_of": 5,
        "model_ready": True,
        "service_model": {"p1_hold": 0.76, "p2_hold": 0.72},
        "first_set_win": {"Alpha": 57.0, "Beta": 43.0},
        "second_set_win": {"Alpha": 55.0, "Beta": 45.0},
        "third_set_win": {"Alpha": 54.0, "Beta": 46.0},
        "fourth_set_win": {"Alpha": 53.0, "Beta": 47.0},
        "fifth_set_win": {"Alpha": 52.0, "Beta": 48.0},
        "second_set_context": {
            "p1_if_p1_wins_set1": 52.0,
            "p1_if_p1_loses_set1": 59.0,
        },
        "autolearn_v84": {"signals": []},
    }


def _candidate(market, pick, line=None, checkpoint=None):
    return core.Candidate(
        key=f"{market}|{checkpoint or ''}|{line or ''}|{pick}",
        label=f"{market} {pick}",
        market=market,
        pick=pick,
        line=line,
        checkpoint=checkpoint,
        prod_score=80.0,
        shadow_scores={},
        path_probability=None,
        evidence_score=80.0,
        agreement=0.5,
        conflict=0.0,
    )


def test_compact_bo5_outcomes_normalize_without_path_explosion():
    outcomes = compact.build_bo5_compact_outcomes(_match())
    assert outcomes
    assert math.isclose(sum(row["prob"] for row in outcomes), 1.0, abs_tol=1e-9)
    # 14 terminal set scores x compact later-set DP stays bounded around 50k,
    # instead of the 202x202 checkpoint cartesian state used by deep BO3.
    assert 1000 < len(outcomes) <= 52000
    assert all(max(row["sets"]) == 3 for row in outcomes)
    assert all(3 <= row["set_count"] <= 5 for row in outcomes)
    assert all(row["p1_games"] + row["p2_games"] == row["total_games"] for row in outcomes)
    assert all("cp2" not in row and "set2_cp4" not in row for row in outcomes)
    assert all(row["bo5_compact_scope"] == compact.SCOPE for row in outcomes)


def test_compact_bo5_keeps_all_final_match_score_families():
    outcomes = compact.build_bo5_compact_outcomes(_match())
    scores = {row["sets"] for row in outcomes}
    assert scores == {(3, 0), (3, 1), (3, 2), (0, 3), (1, 3), (2, 3)}
    by_score = {score: sum(row["prob"] for row in outcomes if row["sets"] == score) for score in scores}
    assert math.isclose(sum(by_score.values()), 1.0, abs_tol=1e-9)
    assert all(value > 0 for value in by_score.values())


def test_bo5_runtime_marks_checkpoint_and_set3_specific_markets_evidence_only(monkeypatch):
    seen = {}

    def fake_run(legs=4):
        outcomes = deep._build_deep_outcomes(_match())
        assert outcomes
        predicate = deep._deep_predicate(core._predicate)
        cp = predicate(_match(), _candidate("game_state", "2:2", checkpoint=4))
        set2cp = predicate(_match(), _candidate("set2_game_state", "2:2", checkpoint=4))
        set3 = predicate(_match(), _candidate("set3_winner", "Alpha"))
        exact_sets = predicate(_match(), _candidate("exact_sets", "5"))
        assert cp is None
        assert set2cp is None
        assert set3 is None
        assert exact_sets is not None
        assert any(exact_sets(row) for row in outcomes)
        text = deep._path_text_v93(next(row for row in outcomes if row["sets"] == (3, 2)))
        assert "mecz 3:2" in text
        seen["count"] = len(outcomes)
        return {"status": "OK", "matches": 1}

    monkeypatch.setattr(deep, "run", fake_run)
    result = runtime.run()
    assert seen["count"] <= 52000
    assert result["runtime_guard_version"] == "v9.3C-runtime-compact-bo5"
    assert result["bo5_scope"] == compact.SCOPE
    assert result["bo5_checkpoint_fabrication"] is False
    assert "game_state" in result["bo5_evidence_only_markets"]
    assert result["external_requests"] == 0


def test_compact_bo5_source_has_no_network_path():
    source = (ROOT / "backend" / "symphony_bo5_compact_v93c.py").read_text(encoding="utf-8").lower()
    for token in ("urlopen", "requests.get", "urllib.request", "httpx", "aiohttp"):
        assert token not in source
