-- Defense-in-depth for iNeed$ SHADOW placement.
-- This guard applies only to NEW rows. Existing bets and settlement updates are untouched.
-- Approved scope mirrors backend/ineed_scope.py:
--   * set1_winner
--   * set1_total / over
--   * game_state at checkpoint 6 with a non-tied exact score summing to 6

create or replace function public.ineed_enforce_shadow_bet_market_scope()
returns trigger
language plpgsql
set search_path = 'public'
as $$
declare
  market_name text := lower(trim(coalesce(new.market, '')));
  selection_name text := lower(trim(coalesce(new.placement_snapshot->>'pick', new.selection, '')));
  checkpoint_text text := trim(coalesce(new.placement_snapshot->>'checkpoint', ''));
  score_text text;
  left_games integer;
  right_games integer;
begin
  if market_name = 'set1_winner' then
    return new;
  end if;

  if market_name = 'set1_total' and selection_name = 'over' then
    return new;
  end if;

  if market_name = 'game_state' then
    if checkpoint_text <> '6' then
      raise exception 'iNeed SHADOW market scope guard: game_state requires checkpoint 6'
        using errcode = '23514';
    end if;

    score_text := regexp_replace(
      trim(coalesce(new.placement_snapshot->>'pick', new.selection, '')),
      '\s+',
      '',
      'g'
    );

    if score_text !~ '^[0-9]+:[0-9]+$' then
      raise exception 'iNeed SHADOW market scope guard: invalid game_state score'
        using errcode = '23514';
    end if;

    left_games := split_part(score_text, ':', 1)::integer;
    right_games := split_part(score_text, ':', 2)::integer;

    if left_games + right_games = 6 and left_games <> right_games then
      return new;
    end if;
  end if;

  raise exception 'iNeed SHADOW market outside approved scope: market=%, selection=%', new.market, new.selection
    using errcode = '23514';
end
$$;

drop trigger if exists ineed_shadow_bet_market_scope_guard on public.ineed_shadow_bets;
create trigger ineed_shadow_bet_market_scope_guard
before insert on public.ineed_shadow_bets
for each row
execute function public.ineed_enforce_shadow_bet_market_scope();

comment on function public.ineed_enforce_shadow_bet_market_scope() is
  'Fail-closed insert guard for iNeed$ SHADOW approved first-set market scope; does not alter calculations or settlements.';
