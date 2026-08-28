from pathlib import Path
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import superbet_line_coverage_v922 as cov


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
        "serve_props_v72": {
            "ready": True,
            "p1": {"aces": {"ready": True, "mean": 6.0}},
            "p2": {"aces": {"ready": True, "mean": 4.0}},
        },
    }


def test_handicap_accepts_any_real_half_line_and_respects_selection_side():
    dist = {(10, 8): 0.60, (8, 10): 0.40}
    match = _match()
    p1 = cov._handicap_probability(dist, match, {"pick": "Player One", "line": -1.5})
    p2 = cov._handicap_probability(dist, match, {"pick": "Player Two", "line": 1.5})
    assert math.isclose(p1["score"], 60.0, abs_tol=1e-9)
    assert math.isclose(p2["score"], 40.0, abs_tol=1e-9)
    assert math.isclose(p1["push_probability"], 0.0, abs_tol=1e-9)
    assert math.isclose(p1["score"] + p2["score"], 100.0, abs_tol=1e-9)


def test_integer_handicap_keeps_push_separate_instead_of_calling_it_a_loss():
    dist = {(10, 8): 0.60, (8, 10): 0.40}
    result = cov._handicap_probability(dist, _match(), {"pick": "Player One", "line": -2.0})
    assert math.isclose(result["score"], 0.0, abs_tol=1e-9)
    assert math.isclose(result["push_probability"], 60.0, abs_tol=1e-9)
    assert math.isclose(result["loss_probability"], 40.0, abs_tol=1e-9)
    assert "push_is_neutral" in result["probability_semantics"]


def test_existing_market_lab_math_builds_all_three_handicap_distributions_locally():
    bundle = cov._distribution_bundle(_match())
    assert bundle["set1"]
    assert bundle["set2"]
    assert bundle["match"]
    assert math.isclose(sum(bundle["set1"].values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(bundle["set2"].values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(bundle["match"].values()), 1.0, abs_tol=1e-9)


def test_bo5_guard_does_not_fabricate_full_match_or_set2_handicap_distribution():
    match = _match()
    match["best_of"] = 5
    bundle = cov._distribution_bundle(match)
    assert bundle["set1"]
    assert bundle["set2"] is None
    assert bundle["match"] is None


def test_most_aces_uses_existing_serve_props_and_exposes_draw_probability():
    dist = cov._most_aces_distribution(_match())
    assert dist is not None
    assert dist["p1"] > dist["p2"]
    assert dist["draw"] > 0
    assert math.isclose(dist["p1"] + dist["p2"] + dist["draw"], 100.0, abs_tol=1e-7)
    result = cov._most_aces_probability(_match(), {"pick": "Player One"}, dist)
    assert result["score"] == dist["p1"]
    assert result["draw_probability"] == dist["draw"]
    assert "approximation" in result["probability_semantics"]


def test_adapter_appends_missing_signals_but_never_overwrites_an_existing_one():
    match = _match()
    s1 = {"market": "match_game_handicap", "pick": "Player One", "line": -2.5, "operator_available": True}
    s2 = {"market": "set1_game_handicap", "pick": "Player One", "line": -1.5, "operator_available": True}
    existing = dict(s1)
    existing.update({"key": cov._selection_key(s1), "score": 77.0, "label": "already calculated"})
    match["superbet_market_v91"] = {
        "canonical_selections": [s1, s2],
        "model_signals": [existing],
        "prices_used": False,
    }
    out = cov.enrich_match(match)
    ctx = out["superbet_market_v91"]
    rows = ctx["model_signals"]
    assert len(rows) == 2
    original = next(row for row in rows if row["key"] == cov._selection_key(s1))
    assert original["score"] == 77.0
    added = next(row for row in rows if row["key"] == cov._selection_key(s2))
    assert added["coverage_adapter_version"] == "v9.2.2"
    assert ctx["coverage_adapter_added"] == 1
    assert ctx["operator_only_count"] == 0
    assert ctx["coverage_adapter_external_requests"] == 0


def test_missing_evidence_stays_operator_only_instead_of_getting_a_fake_probability():
    match = _match()
    match.pop("exact_first_set")
    selection = {"market": "set1_game_handicap", "pick": "Player One", "line": -1.5, "operator_available": True}
    match["superbet_market_v91"] = {"canonical_selections": [selection], "model_signals": []}
    out = cov.enrich_match(match)
    ctx = out["superbet_market_v91"]
    assert ctx["model_signals"] == []
    assert ctx["operator_only_count"] == 1
    assert ctx["coverage_by_market"]["set1_game_handicap"]["coverage"] == 0.0


def test_adapter_source_has_no_network_client_or_request_path():
    source = (BACKEND / "superbet_line_coverage_v922.py").read_text(encoding="utf-8").lower()
    for token in ("urlopen", "requests.get", "urllib.request", "httpx", "aiohttp"):
        assert token not in source
    assert '"external_requests": 0' in source
