from pathlib import Path
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import superbet_line_coverage as cov


def _match():
    return {
        "p1": "Player One",
        "p2": "Player Two",
        "best_of": 3,
        "service_model": {"p1_hold": 78.0, "p2_hold": 74.0},
        "exact_first_set": {"6:4": 30.0, "6:3": 20.0, "7:6": 10.0, "4:6": 20.0, "3:6": 15.0, "6:7": 5.0},
        "second_set_win": {"Player One": 56.0, "Player Two": 44.0},
        "second_set_context": {"p1_if_p1_wins_set1": 58.0, "p1_if_p1_loses_set1": 52.0},
        "third_set_win": {"Player One": 54.0, "Player Two": 46.0},
    }


def test_extended_bundle_reuses_existing_math_and_retains_second_set_paths():
    bundle = cov._extended_bundle(_match())
    assert bundle["set1"]
    assert bundle["set2"]
    assert bundle["match_games"]
    assert bundle["match_sets"]
    assert bundle["set2_paths"]
    assert bundle["any_set_nil"] is not None
    assert math.isclose(sum(bundle["set2"].values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(bundle["match_games"].values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(bundle["match_sets"].values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(bundle["set2_paths"].values()), 1.0, abs_tol=1e-9)


def test_new_audited_families_get_model_probability_but_stay_display_only():
    match = _match()
    selections = [
        {"market": "any_set_to_nil", "pick": "yes"},
        {"market": "set2_exact_score", "pick": "6:4"},
        {"market": "set2_game_state", "pick": "2:2", "checkpoint": 4},
        {"market": "set2_game_state", "pick": "3:3", "checkpoint": 6},
        {"market": "exact_sets", "pick": "3"},
        {"market": "match_games_parity", "pick": "odd"},
        {"market": "set1_games_parity", "pick": "even"},
        {"market": "set2_games_parity", "pick": "odd"},
        {"market": "p1_exactly_1_set", "pick": "yes", "player": "Player One"},
        {"market": "p1_exactly_2_sets", "pick": "yes", "player": "Player One"},
        {"market": "p2_exactly_1_set", "pick": "yes", "player": "Player Two"},
        {"market": "p2_exactly_2_sets", "pick": "yes", "player": "Player Two"},
        {"market": "p1_wins_a_set", "pick": "yes", "player": "Player One"},
        {"market": "p2_wins_a_set", "pick": "yes", "player": "Player Two"},
        {"market": "set_handicap", "pick": "Player One", "line": -1.5},
    ]
    for row in selections:
        row.update({"operator_available": True, "operator_line_verified": True})
    match["superbet_market_v91"] = {"canonical_selections": selections, "model_signals": [], "prices_used": False}
    out = cov.enrich_match(match)
    ctx = out["superbet_market_v91"]
    assert ctx["model_signals"] == []
    assert len(ctx["coverage_shadow_signals"]) == len(selections)
    assert ctx["display_covered_count"] == len(selections)
    assert ctx["operator_only_count"] == 0
    assert ctx["model_coverage"] == 0.0
    assert ctx["display_model_coverage"] == 1.0
    assert ctx["coverage_adapter_version"] == "v9.2.4"
    assert all(row["symphony_actionable"] is False for row in ctx["coverage_shadow_signals"])
    assert all("PENDING_SETTLEMENT" in row["coverage_status"] for row in ctx["coverage_shadow_signals"])


def test_second_set_checkpoint_probability_is_a_real_path_marginal_not_terminal_guess():
    bundle = cov._extended_bundle(_match())
    p22 = cov._set2_checkpoint_probability(bundle["set2_paths"], 4, (2, 2))
    p31 = cov._set2_checkpoint_probability(bundle["set2_paths"], 4, (3, 1))
    p13 = cov._set2_checkpoint_probability(bundle["set2_paths"], 4, (1, 3))
    p40 = cov._set2_checkpoint_probability(bundle["set2_paths"], 4, (4, 0))
    p04 = cov._set2_checkpoint_probability(bundle["set2_paths"], 4, (0, 4))
    assert all(x is not None and x >= 0 for x in (p22, p31, p13, p40, p04))
    assert math.isclose(p22 + p31 + p13 + p40 + p04, 100.0, abs_tol=1e-7)


def test_bo5_guard_keeps_new_full_match_families_uncovered_instead_of_fabricated():
    match = _match()
    match["best_of"] = 5
    bundle = cov._extended_bundle(match)
    assert bundle["set1"]
    assert bundle["set2"] is None
    assert bundle["match_games"] is None
    assert bundle["match_sets"] is None
    assert bundle["set2_paths"] is None
    assert bundle["any_set_nil"] is None


def test_adapter_source_has_no_network_path():
    source = (BACKEND / "superbet_line_coverage.py").read_text(encoding="utf-8").lower()
    for token in ("urlopen", "requests.get", "urllib.request", "httpx", "aiohttp"):
        assert token not in source
    assert '"external_requests":0' in source.replace(" ", "")
