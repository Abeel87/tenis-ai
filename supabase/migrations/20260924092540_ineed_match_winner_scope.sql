-- Change only new V1 SHADOW placement scope to the exact match winner.
-- Existing first-set/game bets and their settlement/update path are untouched.
-- The trigger is already attached to BEFORE INSERT on ineed_shadow_bets.
create or replace function public.ineed_enforce_shadow_bet_market_scope()
returns trigger
language plpgsql
set search_path = 'public'
as $$
begin
  if lower(trim(coalesce(new.market, ''))) = 'match_winner'
     and trim(coalesce(new.selection, '')) <> ''
     and lower(trim(coalesce(new.placement_snapshot->>'market', ''))) = 'match_winner'
     and trim(coalesce(new.placement_snapshot->>'pick', '')) = trim(new.selection)
  then
    return new;
  end if;

  raise exception 'iNeed SHADOW market outside approved match-winner scope: market=%, selection=%',
    new.market, new.selection using errcode = '23514';
end
$$;

comment on function public.ineed_enforce_shadow_bet_market_scope() is
  'Fail-closed new SHADOW placement guard for exact match winner only; old bets retain settlement lifecycle.';
