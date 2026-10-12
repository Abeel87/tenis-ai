from copy import deepcopy

import pytest

from backend.signal_settlement import reconcile_settled, settle_signal_live


def final():
    return {"status": "completed", "p1": "Jake Delaney", "p2": "Marat Sharipov",
            "winner": "Marat Sharipov", "sets": [[3, 6], [4, 6]],
            "completed_sets": [True, True]}


@pytest.mark.parametrize("pick,expected", [("Sharipov, Marat", "hit"),
                                          ("Delaney, Jake", "miss"),
                                          ("Sharipov", "unverifiable"),
                                          ("Unknown Player", "unverifiable")])
def test_full_participant_identity_is_order_independent_and_fail_closed(pick, expected):
    assert settle_signal_live({"market": "match_winner", "pick": pick}, final()) == expected


def test_ambiguous_tokens_and_unknown_winner_are_not_a_loss():
    ambiguous = {**final(), "p1": "Alex Lee", "p2": "Lee Alex", "winner": "Alex Lee"}
    assert settle_signal_live({"market": "match_winner", "pick": "Alex Lee"}, ambiguous) == "unverifiable"
    assert settle_signal_live({"market": "match_winner", "pick": "Jake Delaney"},
                              {**final(), "winner": "Other Player"}) == "unverifiable"


def test_multi_part_name_resolves_only_with_all_tokens():
    f = {**final(), "p2": "Santiago De La Fuente", "winner": "Santiago De La Fuente"}
    assert settle_signal_live({"market": "match_winner", "pick": "De la Fuente, Santiago"}, f) == "hit"
    assert settle_signal_live({"market": "match_winner", "pick": "De la Fuente"}, f) == "unverifiable"


@pytest.mark.parametrize("status", ["completed", "retired"])
def test_set_winner_uses_same_identity_without_changing_retirement_rules(status):
    f = {**final(), "status": status}
    assert settle_signal_live({"market": "set1_winner", "pick": "Sharipov, Marat"}, f) == "hit"
    if status == "retired":
        assert settle_signal_live({"market": "match_winner", "pick": "Sharipov, Marat"}, f) == "void"
        f["completed_sets"] = [False, False]
        assert settle_signal_live({"market": "set1_winner", "pick": "Sharipov, Marat"}, f) == "void"


def test_named_handicap_and_player_total_share_identity_resolution():
    assert settle_signal_live({"market": "match_game_handicap", "pick": "Sharipov, Marat", "line": -2.5}, final()) == "hit"
    assert settle_signal_live({"market": "set_handicap", "pick": "Sharipov, Marat", "line": -1.5}, final()) == "hit"
    assert settle_signal_live({"market": "player_total_games", "player": "Sharipov, Marat", "pick": "over", "line": 11.5}, final()) == "hit"


def test_archive_repair_is_auditable_idempotent_and_preserves_frozen_predictions():
    signal = {"market": "match_winner", "pick": "Sharipov, Marat", "result": "miss",
              "score": 42.55, "settlement_source": "Live Tennis API", "captured_at": "frozen"}
    entry = {"match_id": 1, "p1": "Jake Delaney", "p2": "Marat Sharipov", "status": "settled",
             "settled_at": "original", "result": final(), "playable_signals_v912": [signal],
             "signals": [{"market": "game_state", "result": "hit", "settlement_source": "PBP"}]}
    before = deepcopy(entry)
    out = reconcile_settled([entry])[0]
    assert entry == before
    repaired = out["playable_signals_v912"][0]
    assert repaired["result"] == "hit"
    assert repaired["settlement_corrections"][0]["previous_result"] == "miss"
    assert repaired["settlement_corrections"][0]["previous_source"] == "Live Tennis API"
    assert repaired["settlement_corrections"][0]["corrected_result"] == "hit"
    assert repaired["score"] == 42.55 and repaired["captured_at"] == "frozen"
    assert repaired["pick"] == signal["pick"]
    assert out["settled_at"] == "original" and out["result"] == entry["result"]
    assert out["signals"] == entry["signals"]
    assert reconcile_settled([out]) == [out]


def test_archive_repair_does_not_rewrite_other_semantics_or_unresolved_evidence():
    e = {"p1": "Jake Delaney", "p2": "Marat Sharipov", "status": "settled", "result": final(),
         "signals": [{"market": "match_total", "pick": "over", "line": 1, "result": "miss"},
                     {"market": "match_winner", "pick": "Unknown", "result": "miss"},
                     {"market": "match_winner", "pick": "Sharipov, Marat", "result": "void"}]}
    assert reconcile_settled([e])[0] == e


def test_unresolvable_archived_labels_cannot_train_symphony():
    from backend.symphony2_learning import build_training_rows
    e = {"p1": "Jake Delaney", "p2": "Marat Sharipov", "match_id": 1,
         "captured_at": "2026-10-01T10:00:00Z", "playable_signals_v912": [
             {"market": "match_winner", "pick": "Unknown", "result": "miss",
              "operator": "superbet.pl", "operator_line_verified": True},
             {"market": "match_winner", "pick": "Sharipov, Marat", "result": "hit",
              "operator": "superbet.pl", "operator_line_verified": True}]}
    rows = build_training_rows([e], candidate_markets=set())
    assert len(rows) == 1 and rows[0]["target"] == 1
