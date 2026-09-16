from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ineed_shadow_insert_guard_matches_approved_scope():
    sql = (ROOT / "supabase/migrations/20260916182500_ineed_shadow_market_scope_insert_guard.sql").read_text(encoding="utf-8")

    assert "before insert on public.ineed_shadow_bets" in sql.lower()
    assert "market_name = 'set1_winner'" in sql
    assert "market_name = 'set1_total' and selection_name = 'over'" in sql
    assert "market_name = 'game_state'" in sql
    assert "checkpoint_text <> '6'" in sql
    assert "left_games + right_games = 6 and left_games <> right_games" in sql
    assert "errcode = '23514'" in sql


def test_workflow_run_producers_require_successful_main_source():
    superbet = (ROOT / ".github/workflows/superbet-market-refresh.yml").read_text(encoding="utf-8")
    player_dna = (ROOT / ".github/workflows/player-dna-shadow-refresh.yml").read_text(encoding="utf-8")

    required = (
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.head_branch == 'main'",
    )
    for workflow in (superbet, player_dna):
        for fragment in required:
            assert fragment in workflow
