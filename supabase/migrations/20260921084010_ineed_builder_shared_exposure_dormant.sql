-- LOGIC-12: dormant Bet Builder owner + shared risk-exposure read source.
-- Repository schema only. No reserve RPC, runtime caller, settlement path, or deployment.

create extension if not exists pgcrypto with schema extensions;

create table public.ineed_builder_tickets (
  id uuid primary key default gen_random_uuid(),
  experiment_id uuid not null references public.ineed_experiments(id) on delete cascade,
  composition_id text not null,
  ticket_key text generated always as ('builder-ticket:' || composition_id) stored,
  reservation_key text generated always as ('builder:' || composition_id) stored,
  ticket_snapshot jsonb not null,
  ticket_digest text generated always as (
    encode(extensions.digest(ticket_snapshot::text, 'sha256'), 'hex')
  ) stored,
  status text not null default 'SHADOW_RESERVED',
  stake numeric(14,4) not null,
  currency text not null default 'PLN',
  match_id text not null,
  p1 text not null,
  p2 text not null,
  market_dimensions text[] not null,
  reservation_contract_version text not null,
  created_at timestamptz not null default now(),
  reserved_at timestamptz not null default now(),
  constraint ineed_builder_tickets_status_check check (status = 'SHADOW_RESERVED'),
  constraint ineed_builder_tickets_stake_check check (stake > 0),
  constraint ineed_builder_tickets_currency_check check (currency = 'PLN'),
  constraint ineed_builder_tickets_identity_check check (
    trim(composition_id) <> '' and trim(match_id) <> '' and
    trim(p1) <> '' and trim(p2) <> '' and trim(reservation_contract_version) <> ''
  ),
  constraint ineed_builder_tickets_markets_check check (
    cardinality(market_dimensions) >= 1 and
    array_position(market_dimensions, null) is null and
    array_position(market_dimensions, '') is null
  ),
  constraint ineed_builder_tickets_snapshot_type_check check (
    jsonb_typeof(ticket_snapshot) = 'object'
  ),
  constraint ineed_builder_tickets_snapshot_contract_check check (
    ticket_snapshot @> '{"schema_version":"logic12-builder-ticket-shadow-v1","status":"SHADOW_TICKET_PROPOSED","economic_unit":"BET_BUILDER_COMPOSITION","mode":"SHADOW","operator":"superbet.pl","runtime_publishable":false,"persistence_ready":false,"settlement_ready":false,"settlement_contract_status":"NOT_IMPLEMENTED","automatic_real_betting":false,"reservation_proposal":{"status":"SHADOW_PROPOSED","unit":"BET_BUILDER_COMPOSITION","runtime_publishable":false}}'::jsonb
    and ticket_snapshot->>'ticket_key' = ticket_key
    and ticket_snapshot->>'composition_id' = composition_id
    and ticket_snapshot->>'match_id' = match_id
    and trim(ticket_snapshot->>'p1') = trim(p1)
    and trim(ticket_snapshot->>'p2') = trim(p2)
    and ticket_snapshot #>> '{reservation_proposal,reservation_key}' = reservation_key
    and ticket_snapshot #>> '{reservation_proposal,currency}' = currency
    and (ticket_snapshot #>> '{reservation_proposal,amount}')::numeric = stake
    and (ticket_snapshot #>> '{economics,final_stake}')::numeric = stake
  ),
  unique (experiment_id, ticket_key),
  unique (experiment_id, reservation_key),
  unique (experiment_id, composition_id)
);
create index ineed_builder_tickets_open_idx
  on public.ineed_builder_tickets(experiment_id, status, reserved_at);

alter table public.ineed_builder_tickets enable row level security;
revoke all on table public.ineed_builder_tickets
  from public, anon, authenticated, service_role;
grant select on table public.ineed_builder_tickets to service_role;

alter table public.ineed_bankroll_ledger
  add column builder_ticket_id uuid
    references public.ineed_builder_tickets(id) on delete restrict,
  add constraint ineed_bankroll_ledger_reservation_owner_check
    check (
      entry_type <> 'STAKE_RESERVED'
      or num_nonnulls(bet_id, builder_ticket_id) = 1
    ),
  add constraint ineed_bankroll_ledger_builder_entry_check
    check (
      builder_ticket_id is null
      or (
        entry_type = 'STAKE_RESERVED' and
        bet_id is null and
        source = 'ineed_builder_ticket' and
        source_key like 'reserve:builder:%'
      )
    );

create unique index ineed_ledger_builder_reservation_unique
  on public.ineed_bankroll_ledger(experiment_id, builder_ticket_id)
  where entry_type = 'STAKE_RESERVED' and builder_ticket_id is not null;

create view public.ineed_open_risk_exposures
with (security_invoker = true)
as
select
  b.experiment_id,
  'V1_SINGLE_BET'::text as economic_unit,
  b.status,
  b.stake,
  b.match_id,
  case
    when nullif(trim(coalesce(b.placement_snapshot->>'p1', '')), '') is null
      then array_remove(array[nullif(trim(coalesce(b.placement_snapshot->>'p2', '')), '')], null)::text[]
    when nullif(trim(coalesce(b.placement_snapshot->>'p2', '')), '') is null
      or trim(b.placement_snapshot->>'p2') = trim(b.placement_snapshot->>'p1')
      then array[trim(b.placement_snapshot->>'p1')]::text[]
    else array[trim(b.placement_snapshot->>'p1'), trim(b.placement_snapshot->>'p2')]::text[]
  end as players,
  array[trim(b.market)]::text[] as markets,
  b.id::text as source_id,
  null::text as composition_id
from public.ineed_shadow_bets b
where b.status in ('SHADOW_PLACED', 'PENDING')

union all

select
  t.experiment_id,
  'BET_BUILDER_COMPOSITION'::text as economic_unit,
  t.status,
  t.stake,
  t.match_id,
  array[t.p1, t.p2]::text[] as players,
  t.market_dimensions as markets,
  t.ticket_key as source_id,
  t.composition_id
from public.ineed_builder_tickets t
where t.status = 'SHADOW_RESERVED';

revoke all on table public.ineed_open_risk_exposures
  from public, anon, authenticated, service_role;
grant select on table public.ineed_open_risk_exposures to service_role;

comment on table public.ineed_builder_tickets is
  'Dormant LOGIC-12 SHADOW builder ticket/exposure owner. No runtime writer or settlement path is enabled.';
comment on view public.ineed_open_risk_exposures is
  'Service-only normalized open risk exposure source across V1 single bets and dormant SHADOW builder reservations.';
comment on column public.ineed_bankroll_ledger.builder_ticket_id is
  'Dormant LOGIC-12 builder reservation owner reference; builder settlement is NOT_IMPLEMENTED.';
