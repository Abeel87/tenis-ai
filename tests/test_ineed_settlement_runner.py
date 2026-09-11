from backend.ineed_settlement_runner import (
    final_from_match,
    normalize_open_bets_for_settlement,
)
from backend.ineed_money import build_settlements


def _bet(pick="Diaz Acosta, Facundo"):
    return {
        "id": "bet-1",
        "match_id": "188942",
        "market": "match_winner",
        "selection": pick,
        "status": "PENDING",
        "stake": 6.0,
        "odds": 1.53,
        "placement_snapshot": {
            "match_id": "188942",
            "market": "match_winner",
            "pick": pick,
            "selection": pick,
            "p1": "Sebastian Ofner",
            "p2": "Facundo Diaz Acosta",
        },
    }


def test_normalizes_superbet_surname_given_order_before_settlement():
    rows = normalize_open_bets_for_settlement([_bet()])
    assert rows[0]["placement_snapshot"]["pick"] == "Facundo Diaz Acosta"


def test_normalized_match_winner_settles_as_win():
    bet = normalize_open_bets_for_settlement([_bet()])[0]
    final = {
        "status": "completed",
        "winner": "Facundo Diaz Acosta",
        "p1": "Sebastian Ofner",
        "p2": "Facundo Diaz Acosta",
        "sets": [[5, 7], [2, 6]],
        "completed_sets": [True, True],
        "number_of_sets": 2,
        "total_games": 20,
        "first_set_score": "5:7",
        "match_score": "0:2",
    }
    cfg = {"stake_tax_rate": 0.12, "high_win_tax_threshold_pln": 2280, "high_win_tax_rate": 0.10}
    settlements = build_settlements(
        [bet],
        [{"match_id": "188942", "p1": final["p1"], "p2": final["p2"], "result": final}],
        cfg,
    )
    assert len(settlements) == 1
    assert settlements[0]["outcome"] == "WIN"
    assert settlements[0]["payout"] == 8.0784


def test_live_result_requires_score_and_winner_to_agree():
    bet = _bet()
    good = {
        "winner": 2,
        "event_status": "Finished",
        "score": {"games": [[5, 2], [7, 6]]},
    }
    final = final_from_match(good, bet)
    assert final is not None
    assert final["winner"] == "Facundo Diaz Acosta"

    inconsistent = {
        "winner": 1,
        "event_status": "Finished",
        "score": {"games": [[5, 2], [7, 6]]},
    }
    assert final_from_match(inconsistent, bet) is None
