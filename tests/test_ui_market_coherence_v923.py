from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "symphony-playable-detail-guard-v915.js"


def _text() -> str:
    return JS.read_text(encoding="utf-8")


def test_playable_symphony_rejects_obvious_same_market_conflicts():
    text = _text()
    assert "function selectionsConflict" in text
    assert "function compositionCoherent" in text
    assert "pair.has('over') && pair.has('under')" in text
    assert "api.compositionPlayable(match,comp) && compositionCoherent(api,comp)" in text
    assert "'match_winner','set1_winner','set2_winner','set3_winner'" in text
    assert "'exact_match_score','set1_exact_score','set2_exact_score','set3_exact_score','game_state'" in text


def test_superbet_market_list_is_collapsible_without_removing_data():
    text = _text()
    assert "v923-market-collapsed" in text
    assert "Pokaż realne rynki Superbet" in text
    assert "Zwiń realne rynki Superbet" in text
    assert "Lista rynków jest zwinięta dla czytelności" in text


def test_exact_scores_are_humanized_with_player_sides():
    text = _text()
    assert "Dokładny wynik · ${p1}" in text
    assert "set([123]) exact score" in text
    assert "game state" in text
    assert "shortName(match?.p1)" in text
    assert "shortName(match?.p2)" in text


def test_v923_is_ui_guard_only_not_model_math_or_learning():
    text = _text()
    forbidden_writes = [
        "final_score =",
        "adaptive_prod_score =",
        "probability =",
        "joint_probability =",
        "path_probability =",
    ]
    for token in forbidden_writes:
        assert token not in text
    assert "training" in text  # documentation explicitly states it is untouched
    assert "settlement" in text
