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


def test_match_total_ladder_allows_one_over_and_one_under():
    compatible = comparison_compatible(core._compatible)
    under_24 = candidate("match_total|24.5|under", "match_total", "under", 24.5)
    under_25 = candidate("match_total|25.5|under", "match_total", "under", 25.5)
    over_18 = candidate("match_total|18.5|over", "match_total", "over", 18.5)
    over_19 = candidate("match_total|19.5|over", "match_total", "over", 19.5)
    over_24 = candidate("match_total|24.5|over", "match_total", "over", 24.5)

    assert compatible(under_24, under_25) is False
    assert compatible(over_18, over_19) is False
    assert compatible(over_18, under_24) is True
    # Same exact line on opposite sides is contradictory and remains blocked.
    assert compatible(under_24, over_24) is False


def test_set_total_ladders_use_one_per_side_rule_too():
    compatible = comparison_compatible(core._compatible)
    set1_over_8 = candidate("set1_total|8.5|over", "set1_total", "over", 8.5)
    set1_over_9 = candidate("set1_total|9.5|over", "set1_total", "over", 9.5)
    set1_under_10 = candidate("set1_total|10.5|under", "set1_total", "under", 10.5)
    sets_over = candidate("total_sets|2.5|over", "total_sets", "over", 2.5)
    sets_under = candidate("total_sets|3.5|under", "total_sets", "under", 3.5)

    assert compatible(set1_over_8, set1_over_9) is False
    assert compatible(set1_over_8, set1_under_10) is True
    assert compatible(sets_over, sets_under) is True
    # Different market families may still coexist.
    assert compatible(set1_over_8, sets_over) is True


def test_verified_serve_markets_can_still_be_combined():
    # Compatibility itself remains valid once a real bookmaker line has been
    # verified. The evidence adapter now blocks model-made serve thresholds
    # before they ever reach this stage.
    compatible = comparison_compatible(core._compatible)
    most_aces = candidate("most_aces|A", "most_aces", "A")
    player_aces = candidate("player_aces|p1|4.5|over", "player_aces", "over", 4.5)
    player_df = candidate("player_double_faults|p1|3.5|over", "player_double_faults", "over", 3.5)

    assert compatible(most_aces, player_aces) is True
    assert compatible(player_aces, player_df) is True


def test_composer_never_emits_more_than_one_match_total_per_side(monkeypatch):
    candidates = [
        candidate("match_total|23.5|under", "match_total", "under", 23.5, 94),
        candidate("match_total|24.5|under", "match_total", "under", 24.5, 93),
        candidate("match_total|18.5|over", "match_total", "over", 18.5, 92),
        candidate("match_total|19.5|over", "match_total", "over", 19.5, 91),
        candidate("player_aces|p1|4.5|over", "player_aces", "over", 4.5, 88),
        candidate("player_double_faults|p1|3.5|over", "player_double_faults", "over", 3.5, 87),
        candidate("most_aces|A", "most_aces", "A", None, 86),
        candidate("match_winner|A", "match_winner", "A", None, 85),
    ]

    monkeypatch.setattr(core, "_compatible", comparison_compatible(core._compatible))
    comps = _one_pass_compositions({"p1": "A", "p2": "B"}, candidates, [])
    assert comps

    def check(scenario):
        legs = scenario.get("selection") or []
        totals = [leg for leg in legs if leg.get("market") == "match_total"]
        unders = [leg for leg in totals if str(leg.get("pick") or "").casefold() == "under"]
        overs = [leg for leg in totals if str(leg.get("pick") or "").casefold() == "over"]
        assert len(unders) <= 1
        assert len(overs) <= 1
        assert len(totals) <= 2

    for comp in comps.values():
        check(comp)
        for alt in comp.get("alternatives") or []:
            check(alt)
