from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ineed_shadow_insert_guard_matches_approved_scope():
    original = (ROOT / "supabase/migrations/20260916182500_ineed_shadow_market_scope_insert_guard.sql").read_text(encoding="utf-8")
    sql = (ROOT / "supabase/migrations/20260924092540_ineed_match_winner_scope.sql").read_text(encoding="utf-8")

    assert "before insert on public.ineed_shadow_bets" in original.lower()
    assert "create or replace function public.ineed_enforce_shadow_bet_market_scope()" in sql
    assert "new.market, ''))) = 'match_winner'" in sql
    assert "new.placement_snapshot->>'market', ''))) = 'match_winner'" in sql
    assert "new.placement_snapshot->>'pick', '')) = trim(new.selection)" in sql
    assert "set1_winner" not in sql
    assert "set1_total" not in sql
    assert "game_state" not in sql
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
