-- LOGIC-12: preserve the live V1 settlement mutex and migrate only open-exposure bookkeeping.
-- Repository migration only; no builder settlement semantics, writer, or deployment.

create or replace function public.ineed_system_settle_bet(
  target_bet_id uuid,
  settlement_outcome text,
  settlement_payout numeric,
  settlement_detail jsonb default '{}'::jsonb
)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare
  b public.ineed_shadow_bets%rowtype;
  e public.ineed_experiments%rowtype;
  available numeric(14,4);
  other_exposure numeric(14,4);
  credit numeric(14,4);
  after_available numeric(14,4);
  after_equity numeric(14,4);
  entry text;
begin
  settlement_outcome := upper(trim(settlement_outcome));
  if settlement_outcome not in ('WIN','LOSS','VOID','CANCELLED') then
    raise exception 'Invalid iNeed settlement outcome';
  end if;

  select * into b from public.ineed_shadow_bets where id=target_bet_id for update;
  if not found then raise exception 'iNeed bet not found'; end if;
  if b.status in ('WIN','LOSS','VOID','CANCELLED','SETTLED') then
    return jsonb_build_object('status','IDEMPOTENT','bet_id',b.id,'outcome',b.status);
  end if;

  -- Preserve the mutex already present in the live production RPC.
  select * into e from public.ineed_experiments where id=b.experiment_id for update;
  if not found then raise exception 'iNeed experiment not found'; end if;

  select coalesce((
    select bankroll_after
    from public.ineed_bankroll_ledger
    where experiment_id=e.id
    order by created_at desc,id desc
    limit 1
  ),0) into available;

  credit := case
    when settlement_outcome='WIN' then greatest(coalesce(settlement_payout,0),0)
    when settlement_outcome in ('VOID','CANCELLED') then b.stake
    else 0
  end;
  entry := case settlement_outcome
    when 'WIN' then 'BET_WIN'
    when 'LOSS' then 'BET_LOSS'
    when 'VOID' then 'BET_VOID'
    else 'BET_CANCELLED'
  end;
  after_available := available + credit;
  insert into public.ineed_bankroll_ledger(
    experiment_id,entry_type,amount,source,source_key,bet_id,bankroll_before,bankroll_after
  ) values(
    e.id,entry,credit,'ineed_settlement','settle:'||b.id::text,b.id,available,after_available
  ) on conflict(experiment_id,source_key) do nothing;

  -- The target V1 bet is still open in the view until the update below, so exclude it explicitly.
  -- All other V1 open bets and future SHADOW_RESERVED builder exposures remain included.
  select coalesce(sum(r.stake),0) into other_exposure
  from public.ineed_open_risk_exposures r
  where r.experiment_id=e.id
    and not (
      r.economic_unit='V1_SINGLE_BET'
      and r.source_id=b.id::text
    );
  after_equity := after_available + other_exposure;

  update public.ineed_shadow_bets
  set status=settlement_outcome,
      payout=credit,
      net_profit=credit-b.stake,
      bankroll_after=after_equity,
      settlement_snapshot=settlement_detail,
      settled_at=now()
  where id=b.id;

  update public.ineed_signals set status=settlement_outcome,updated_at=now() where id=b.signal_id;
  return jsonb_build_object(
    'status','SETTLED',
    'bet_id',b.id,
    'outcome',settlement_outcome,
    'bankroll_after',after_equity
  );
end $$;

revoke all on function public.ineed_system_settle_bet(uuid,text,numeric,jsonb)
  from public,anon,authenticated;
grant execute on function public.ineed_system_settle_bet(uuid,text,numeric,jsonb)
  to service_role;
