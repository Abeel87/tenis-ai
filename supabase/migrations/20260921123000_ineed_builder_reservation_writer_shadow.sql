-- LOGIC-12: dormant SHADOW Bet Builder reservation writer.
-- Service-role only; no runtime caller. The experiment config flag is absent by default.
-- Builder settlement remains NOT_IMPLEMENTED and real-money execution remains disabled.

create or replace function public.ineed_system_reserve_builder_ticket(
  target_experiment_id uuid,
  ticket_snapshot jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  e public.ineed_experiments%rowtype;
  existing public.ineed_builder_tickets%rowtype;
  ticket_row public.ineed_builder_tickets%rowtype;
  ledger_row public.ineed_bankroll_ledger%rowtype;
  composition_id text;
  expected_ticket_key text;
  expected_reservation_key text;
  expected_digest text;
  reservation_contract_version constant text := 'logic12-builder-reservation-shadow-v1';
  provenance jsonb;
  phase4 jsonb;
  reservation jsonb;
  leg_count integer;
  component_count integer;
  component_distinct integer;
  market_dimensions text[];
  leg_markets text[];
  match_id text;
  p1 text;
  p2 text;
  p1_norm text;
  p2_norm text;
  stake_value numeric(14,4);
  available numeric(14,4);
  total_exposure numeric(14,4);
  match_exposure numeric(14,4);
  player_exposure numeric(14,4);
  one_market_exposure numeric(14,4);
  equity numeric(14,4);
  peak_equity numeric(14,4);
  drawdown numeric;
  risk_name text;
  stake_multiplier numeric;
  exposure_multiplier numeric;
  single_cap numeric(14,4);
  total_cap numeric(14,4);
  match_cap numeric(14,4);
  player_cap numeric(14,4);
  market_cap numeric(14,4);
  market_name text;
begin
  select * into e
  from public.ineed_experiments
  where id = target_experiment_id
  for update;

  if not found then
    raise exception 'INEED_EXPERIMENT_NOT_FOUND';
  end if;
  if e.status <> 'ACTIVE' or e.mode <> 'SHADOW' or e.operator <> 'superbet.pl' then
    raise exception 'INEED_EXPERIMENT_NOT_ACTIVE_SHADOW';
  end if;
  if coalesce(e.config->>'automatic_real_betting', 'false') <> 'false' then
    raise exception 'REAL_BETTING_MUST_REMAIN_DISABLED';
  end if;
  if lower(coalesce(e.config #>> '{builder_reservation,enabled}', 'false')) <> 'true'
     or coalesce(e.config #>> '{builder_reservation,contract_version}', '') <> reservation_contract_version then
    raise exception 'BUILDER_RESERVATION_DISABLED';
  end if;

  if jsonb_typeof(ticket_snapshot) <> 'object' then
    raise exception 'INVALID_BUILDER_TICKET';
  end if;
  if ticket_snapshot->>'schema_version' <> 'logic12-builder-ticket-shadow-v1'
     or ticket_snapshot->>'status' <> 'SHADOW_TICKET_PROPOSED'
     or ticket_snapshot->>'economic_unit' <> 'BET_BUILDER_COMPOSITION'
     or ticket_snapshot->>'mode' <> 'SHADOW'
     or ticket_snapshot->>'operator' <> 'superbet.pl'
     or ticket_snapshot->>'runtime_publishable' is distinct from 'false'
     or ticket_snapshot->>'persistence_ready' is distinct from 'false'
     or ticket_snapshot->>'settlement_ready' is distinct from 'false'
     or ticket_snapshot->>'settlement_contract_status' <> 'NOT_IMPLEMENTED'
     or ticket_snapshot->>'automatic_real_betting' is distinct from 'false' then
    raise exception 'INVALID_BUILDER_TICKET_CONTRACT';
  end if;

  composition_id := nullif(trim(ticket_snapshot->>'composition_id'), '');
  match_id := nullif(trim(ticket_snapshot->>'match_id'), '');
  p1 := nullif(trim(ticket_snapshot->>'p1'), '');
  p2 := nullif(trim(ticket_snapshot->>'p2'), '');
  if composition_id is null or match_id is null or p1 is null or p2 is null then
    raise exception 'INVALID_BUILDER_IDENTITY';
  end if;
  expected_ticket_key := 'builder-ticket:' || composition_id;
  expected_reservation_key := 'builder:' || composition_id;
  if ticket_snapshot->>'ticket_key' <> expected_ticket_key then
    raise exception 'BUILDER_TICKET_KEY_MISMATCH';
  end if;

  reservation := ticket_snapshot->'reservation_proposal';
  if jsonb_typeof(reservation) <> 'object'
     or reservation->>'status' <> 'SHADOW_PROPOSED'
     or reservation->>'unit' <> 'BET_BUILDER_COMPOSITION'
     or reservation->>'reservation_key' <> expected_reservation_key
     or reservation->>'composition_id' <> composition_id
     or reservation->>'currency' <> 'PLN'
     or reservation->>'runtime_publishable' is distinct from 'false'
     or jsonb_typeof(reservation->'amount') <> 'number'
     or jsonb_typeof(ticket_snapshot #> '{economics,final_stake}') <> 'number' then
    raise exception 'INVALID_BUILDER_RESERVATION_PROPOSAL';
  end if;
  stake_value := (reservation->>'amount')::numeric;
  if stake_value <= 0
     or (ticket_snapshot #>> '{economics,final_stake}')::numeric <> stake_value then
    raise exception 'BUILDER_STAKE_MISMATCH';
  end if;

  provenance := ticket_snapshot->'combined_price_provenance';
  if jsonb_typeof(provenance) <> 'object'
     or provenance->>'operator_verified' is distinct from 'true'
     or provenance->>'freshness_verified' is distinct from 'true'
     or provenance->>'quote_kind' <> 'BET_BUILDER_COMBINED'
     or nullif(trim(provenance->>'source'), '') is null
     or nullif(trim(provenance->>'odds_timestamp'), '') is null
     or nullif(trim(provenance->>'source_event_id'), '') is null
     or nullif(trim(provenance->>'operator_combination_selection_id'), '') is null
     or nullif(trim(provenance->>'source_url'), '') is null
     or jsonb_typeof(provenance->'component_selection_ids') <> 'array' then
    raise exception 'INVALID_BUILDER_OPERATOR_PROVENANCE';
  end if;

  if jsonb_typeof(ticket_snapshot->'legs') <> 'array'
     or jsonb_typeof(ticket_snapshot->'leg_count') <> 'number' then
    raise exception 'INVALID_BUILDER_LEGS';
  end if;
  leg_count := (ticket_snapshot->>'leg_count')::integer;
  if leg_count < 2 or jsonb_array_length(ticket_snapshot->'legs') <> leg_count then
    raise exception 'INVALID_BUILDER_LEGS';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(ticket_snapshot->'legs') leg
    where jsonb_typeof(leg) <> 'object'
       or nullif(trim(leg->>'market'), '') is null
       or nullif(trim(leg->>'operator_market_id'), '') is null
       or nullif(trim(leg->>'operator_outcome_id'), '') is null
       or leg->>'fixture_line_verified' is distinct from 'true'
  ) then
    raise exception 'INVALID_BUILDER_LEGS';
  end if;
  select count(*), count(distinct trim(value))
  into component_count, component_distinct
  from jsonb_array_elements_text(provenance->'component_selection_ids') component(value)
  where nullif(trim(value), '') is not null;
  if component_count <> leg_count or component_distinct <> leg_count then
    raise exception 'INVALID_BUILDER_COMPONENT_IDENTITY';
  end if;
  if ticket_snapshot->'component_selection_ids' <> provenance->'component_selection_ids'
     or ticket_snapshot->>'source' <> provenance->>'source'
     or ticket_snapshot->>'odds_timestamp' <> provenance->>'odds_timestamp'
     or ticket_snapshot->>'source_event_id' <> provenance->>'source_event_id'
     or ticket_snapshot->>'operator_combination_selection_id' <> provenance->>'operator_combination_selection_id'
     or ticket_snapshot->>'source_url' <> provenance->>'source_url' then
    raise exception 'BUILDER_PROVENANCE_MISMATCH';
  end if;

  phase4 := ticket_snapshot->'phase4_snapshot';
  if jsonb_typeof(phase4) <> 'object'
     or phase4->>'operator' <> 'superbet.pl'
     or phase4->>'mode' <> 'SHADOW'
     or phase4->>'economic_unit' <> 'BET_BUILDER_COMPOSITION'
     or phase4->>'composition_id' <> composition_id
     or trim(phase4->>'match_id') <> match_id
     or trim(phase4->>'p1') <> p1
     or trim(phase4->>'p2') <> p2
     or phase4->>'automatic_real_betting' is distinct from 'false'
     or jsonb_typeof(phase4->'builder_markets') <> 'array'
     or jsonb_typeof(phase4->'final_stake') <> 'number' then
    raise exception 'INVALID_PHASE4_SNAPSHOT';
  end if;
  if phase4->'combined_price_provenance' <> provenance
     or (phase4->>'final_stake')::numeric <> stake_value
     or jsonb_typeof(ticket_snapshot->'joint_probability') <> 'number'
     or jsonb_typeof(ticket_snapshot->'combined_odds') <> 'number'
     or jsonb_typeof(phase4->'joint_probability') <> 'number'
     or jsonb_typeof(phase4->'combined_odds') <> 'number'
     or (phase4->>'joint_probability')::numeric <> (ticket_snapshot->>'joint_probability')::numeric
     or (phase4->>'combined_odds')::numeric <> (ticket_snapshot->>'combined_odds')::numeric
     or (ticket_snapshot->>'joint_probability')::numeric < 0
     or (ticket_snapshot->>'joint_probability')::numeric > 100
     or (ticket_snapshot->>'combined_odds')::numeric <= 1 then
    raise exception 'BUILDER_EVIDENCE_MISMATCH';
  end if;

  select array_agg(market_name order by market_name)
  into market_dimensions
  from (
    select distinct trim(value) as market_name
    from jsonb_array_elements_text(phase4->'builder_markets') market(value)
    where nullif(trim(value), '') is not null
  ) normalized_markets;
  if market_dimensions is null
     or cardinality(market_dimensions) < 1
     or cardinality(market_dimensions) <> jsonb_array_length(phase4->'builder_markets') then
    raise exception 'INVALID_BUILDER_MARKETS';
  end if;

  select array_agg(market_name order by market_name)
  into leg_markets
  from (
    select distinct trim(leg->>'market') as market_name
    from jsonb_array_elements(ticket_snapshot->'legs') leg
  ) normalized_leg_markets;
  if leg_markets is distinct from market_dimensions then
    raise exception 'BUILDER_MARKET_DIMENSION_MISMATCH';
  end if;
  expected_digest := encode(extensions.digest(ticket_snapshot::text, 'sha256'), 'hex');

  select * into existing
  from public.ineed_builder_tickets
  where experiment_id = e.id and ticket_key = expected_ticket_key;
  if found then
    if existing.ticket_digest <> expected_digest then
      raise exception 'IMMUTABLE_TICKET_CONFLICT';
    end if;
    select * into ledger_row
    from public.ineed_bankroll_ledger
    where experiment_id = e.id
      and entry_type = 'STAKE_RESERVED'
      and builder_ticket_id = existing.id;
    if not found
       or ledger_row.source <> 'ineed_builder_ticket'
       or ledger_row.source_key <> 'reserve:' || expected_reservation_key
       or ledger_row.amount <> -existing.stake then
      raise exception 'BUILDER_RESERVATION_INCONSISTENT';
    end if;
    return jsonb_build_object(
      'status','IDEMPOTENT',
      'builder_ticket_id',existing.id,
      'ticket_key',existing.ticket_key,
      'reservation_key',existing.reservation_key,
      'stake',existing.stake,
      'available_after',ledger_row.bankroll_after
    );
  end if;

  select coalesce((
    select bankroll_after
    from public.ineed_bankroll_ledger
    where experiment_id = e.id
    order by created_at desc, id desc
    limit 1
  ),0) into available;

  select coalesce(sum(r.stake),0)
  into total_exposure
  from public.ineed_open_risk_exposures r
  where r.experiment_id = e.id;

  select coalesce(sum(r.stake),0)
  into match_exposure
  from public.ineed_open_risk_exposures r
  where r.experiment_id = e.id
    and r.match_id = trim(ticket_snapshot->>'match_id');

  p1_norm := lower(trim(p1));
  p2_norm := lower(trim(p2));
  select coalesce(sum(r.stake),0)
  into player_exposure
  from public.ineed_open_risk_exposures r
  where r.experiment_id = e.id
    and exists (
      select 1
      from unnest(r.players) player_name
      where lower(trim(player_name)) in (p1_norm, p2_norm)
    );

  equity := available + total_exposure;
  select greatest(
    e.starting_bankroll,
    equity,
    coalesce(max(bankroll_after), e.starting_bankroll)
  ) into peak_equity
  from public.ineed_shadow_bets
  where experiment_id = e.id and bankroll_after is not null;

  drawdown := case
    when peak_equity > 0 then greatest(0,(peak_equity-equity)/peak_equity)
    else 0
  end;
  risk_name := case
    when drawdown >= (e.config->'drawdown'->>'halted')::numeric then 'HALTED'
    when drawdown >= (e.config->'drawdown'->>'defensive')::numeric then 'DEFENSIVE'
    when drawdown >= (e.config->'drawdown'->>'caution')::numeric then 'CAUTION'
    else 'NORMAL'
  end;
  if risk_name = 'HALTED' then
    raise exception 'INEED_RISK_ENGINE_HALTED';
  end if;

  stake_multiplier := coalesce(
    (e.config->'risk_profiles'->risk_name->>'stake_multiplier')::numeric,1
  );
  exposure_multiplier := coalesce(
    (e.config->'risk_profiles'->risk_name->>'exposure_multiplier')::numeric,1
  );
  if stake_value < (e.config->>'minimum_stake')::numeric then
    raise exception 'BUILDER_STAKE_BELOW_MINIMUM';
  end if;
  if stake_value > available then
    raise exception 'BUILDER_INSUFFICIENT_AVAILABLE_CAPITAL';
  end if;

  single_cap := equity * (e.config->>'max_single_bet_pct')::numeric * stake_multiplier;
  total_cap := equity * (e.config->>'max_total_exposure_pct')::numeric * exposure_multiplier;
  match_cap := equity * (e.config->>'max_match_exposure_pct')::numeric * exposure_multiplier;
  player_cap := equity * (e.config->>'max_player_exposure_pct')::numeric * exposure_multiplier;
  market_cap := equity * (e.config->>'max_market_exposure_pct')::numeric * exposure_multiplier;

  if stake_value > single_cap + 0.0001 then
    raise exception 'BUILDER_SINGLE_BET_EXPOSURE_LIMIT';
  end if;
  if total_exposure + stake_value > total_cap + 0.0001 then
    raise exception 'BUILDER_TOTAL_EXPOSURE_LIMIT';
  end if;
  if match_exposure + stake_value > match_cap + 0.0001 then
    raise exception 'BUILDER_MATCH_EXPOSURE_LIMIT';
  end if;
  if player_exposure + stake_value > player_cap + 0.0001 then
    raise exception 'BUILDER_PLAYER_CORRELATION_LIMIT';
  end if;

  foreach market_name in array market_dimensions loop
    select coalesce(sum(r.stake),0)
    into one_market_exposure
    from public.ineed_open_risk_exposures r
    where r.experiment_id = e.id
      and exists (
        select 1
        from unnest(r.markets) existing_market
        where trim(existing_market) = market_name
      );
    if one_market_exposure + stake_value > market_cap + 0.0001 then
      raise exception 'BUILDER_MARKET_EXPOSURE_LIMIT:%', market_name;
    end if;
  end loop;

  insert into public.ineed_builder_tickets(
    experiment_id,
    composition_id,
    ticket_snapshot,
    status,
    stake,
    currency,
    match_id,
    p1,
    p2,
    market_dimensions,
    reservation_contract_version
  ) values (
    e.id,
    composition_id,
    ticket_snapshot,
    'SHADOW_RESERVED',
    stake_value,
    'PLN',
    match_id,
    p1,
    p2,
    market_dimensions,
    reservation_contract_version
  ) returning * into ticket_row;

  if ticket_row.ticket_digest <> expected_digest
     or ticket_row.ticket_key <> expected_ticket_key
     or ticket_row.reservation_key <> expected_reservation_key then
    raise exception 'BUILDER_DURABLE_IDENTITY_MISMATCH';
  end if;

  insert into public.ineed_bankroll_ledger(
    experiment_id,
    entry_type,
    amount,
    source,
    source_key,
    builder_ticket_id,
    bankroll_before,
    bankroll_after
  ) values (
    e.id,
    'STAKE_RESERVED',
    -stake_value,
    'ineed_builder_ticket',
    'reserve:' || expected_reservation_key,
    ticket_row.id,
    available,
    available - stake_value
  ) returning * into ledger_row;

  return jsonb_build_object(
    'status','RESERVED',
    'builder_ticket_id',ticket_row.id,
    'ticket_key',ticket_row.ticket_key,
    'reservation_key',ticket_row.reservation_key,
    'stake',ticket_row.stake,
    'available_after',ledger_row.bankroll_after,
    'risk_state',risk_name,
    'drawdown',drawdown,
    'automatic_real_betting',false
  );
end $$;

revoke all on function public.ineed_system_reserve_builder_ticket(uuid,jsonb)
  from public, anon, authenticated;
grant execute on function public.ineed_system_reserve_builder_ticket(uuid,jsonb)
  to service_role;

comment on function public.ineed_system_reserve_builder_ticket(uuid,jsonb) is
  'LOGIC-12 dormant SHADOW-only atomic builder reservation writer. Requires explicit experiment builder_reservation enable flag; no runtime caller or builder settlement.';
