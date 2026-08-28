from backend import symphony_engine_v90 as core
from backend.symphony_c4 import comparison_compatible
from backend.symphony_engine_v90 import Candidate
from backend.symphony_engine_v90c import _one_pass_compositions


def candidate(key, market, pick, line=None, score=82):
    return Candidate(
        key=key,
        label=key,
        market=market,
        pick=pick,
        line=line,
        checkpoint=None,
        prod_score=score,
        shadow_scores={},
        path_probability=None,
        evidence_score=score,
        agreement=0.5,
        conflict=0.0,
    )


def test_match_total_ladder_allows_only_one_line():
    compatible = comparison_compatible(core._compatible)
    under_24 = candidate("match_total|24.5|under", "match_total", "under", 24.5)
    under_25 = candidate("match_total|25.5|under", "match_total", "under", 25.5)
    over_24 = candidate("match_total|24.5|over", "match_total", "over", 24.5)

    assert compatible(under_24, under_25) is False
    assert compatible(under_24, over_24) is False


def test_set_total_ladders_are_single_selection_too():
    compatible = comparison_compatible(core._compatible)
    set1_a = candidate("set1_total|8.5|over", "set1_total", "over", 8.5)
    set1_b = candidate("set1_total|9.5|over", "set1_total", "over", 9.5)
    sets_a = candidate("total_sets|2.5|over", "total_sets", "over", 2.5)
    sets_b = candidate("total_sets|3.5|under", "total_sets", "under", 3.5)

    assert compatible(set1_a, set1_b) is False
    assert compatible(sets_a, sets_b) is False
    # Different market families may still coexist.
    assert compatible(set1_a, sets_a) is True


def test_serve_markets_can_still_be_combined():
    compatible = comparison_compatible(core._compatible)
    most_aces = candidate("most_aces|A", "most_aces", "A")
    player_aces = candidate("player_aces|p1|0.5|over", "player_aces", "over", 0.5)
    player_df = candidate("player_double_faults|p1|1.5|over", "player_double_faults", "over", 1.5)

    assert compatible(most_aces, player_aces) is True
    assert compatible(player_aces, player_df) is True


def test_composer_never_emits_multiple_match_total_lines(monkeypatch):
    candidates = [
        candidate("match_total|23.5|under", "match_total", "under", 23.5, 94),
        candidate("match_total|24.5|under", "match_total", "under", 24.5, 93),
        candidate("match_total|25.5|under", "match_total", "under", 25.5, 92),
        candidate("player_aces|p1|0.5|over", "player_aces", "over", 0.5, 88),
        candidate("player_double_faults|p1|1.5|over", "player_double_faults", "over", 1.5, 87),
        candidate("most_aces|A", "most_aces", "A", None, 86),
        candidate("match_winner|A", "match_winner", "A", None, 85),
    ]

    monkeypatch.setattr(core, "_compatible", comparison_compatible(core._compatible))
    comps = _one_pass_compositions({"p1": "A", "p2": "B"}, candidates, [])
    assert comps

    def check(scenario):
        legs = scenario.get("selection") or []
        assert sum(1 for leg in legs if leg.get("market") == "match_total") <= 1

    for comp in comps.values():
        check(comp)
        for alt in comp.get("alternatives") or []:
            check(alt)
