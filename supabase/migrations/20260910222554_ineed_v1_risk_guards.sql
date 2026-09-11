update public.ineed_experiments set config=jsonb_set(jsonb_set(config,'{max_player_exposure_pct}','0.03'::jsonb,true),'{max_market_exposure_pct}','0.15'::jsonb,true) where status='ACTIVE';

create or replace function public.ineed_system_place_bet(target_signal_id uuid)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare
  s public.ineed_signals%rowtype; e public.ineed_experiments%rowtype; existing public.ineed_shadow_bets%rowtype;
  available numeric(14,4); total_exposure numeric(14,4); match_exposure numeric(14,4); player_exposure numeric(14,4); market_exposure numeric(14,4);
  equity numeric(14,4); peak_equity numeric(14,4); drawdown numeric; risk_name text; stake_multiplier numeric; exposure_multiplier numeric;
  stake_value numeric(14,4); bet_row public.ineed_shadow_bets%rowtype; single_cap numeric(14,4); total_cap numeric(14,4); match_cap numeric(14,4); player_cap numeric(14,4); market_cap numeric(14,4); p1 text; p2 text;
begin
  select * into s from public.ineed_signals where id=target_signal_id for update; if not found then raise exception 'iNeed signal not found'; end if;
  select * into e from public.ineed_experiments where id=s.experiment_id for update; if e.status<>'ACTIVE' or e.mode<>'SHADOW' then raise exception 'iNeed experiment is not active SHADOW'; end if;
  select * into existing from public.ineed_shadow_bets where signal_id=s.id; if found then return jsonb_build_object('status','IDEMPOTENT','bet_id',existing.id); end if;
  if s.status<>'QUALIFIED' then raise exception 'iNeed signal is not QUALIFIED'; end if;
  p1:=lower(trim(coalesce(s.current_snapshot->>'p1',''))); p2:=lower(trim(coalesce(s.current_snapshot->>'p2',''))); if p1='' or p2='' then raise exception 'iNeed player exposure context missing'; end if;
  select coalesce((select bankroll_after from public.ineed_bankroll_ledger where experiment_id=e.id order by created_at desc,id desc limit 1),0) into available;
  select coalesce(sum(stake),0) into total_exposure from public.ineed_shadow_bets where experiment_id=e.id and status in ('SHADOW_PLACED','PENDING');
  select coalesce(sum(stake),0) into match_exposure from public.ineed_shadow_bets where experiment_id=e.id and match_id=s.match_id and status in ('SHADOW_PLACED','PENDING');
  select coalesce(sum(stake),0) into market_exposure from public.ineed_shadow_bets where experiment_id=e.id and market=s.market and status in ('SHADOW_PLACED','PENDING');
  select coalesce(sum(stake),0) into player_exposure from public.ineed_shadow_bets b where b.experiment_id=e.id and b.status in ('SHADOW_PLACED','PENDING') and (lower(trim(coalesce(b.placement_snapshot->>'p1',''))) in (p1,p2) or lower(trim(coalesce(b.placement_snapshot->>'p2',''))) in (p1,p2));
  equity:=available+total_exposure;
  select greatest(e.starting_bankroll,equity,coalesce(max(bankroll_after),e.starting_bankroll)) into peak_equity from public.ineed_shadow_bets where experiment_id=e.id and bankroll_after is not null;
  drawdown:=case when peak_equity>0 then greatest(0,(peak_equity-equity)/peak_equity) else 0 end;
  risk_name:=case when drawdown>=(e.config->'drawdown'->>'halted')::numeric then 'HALTED' when drawdown>=(e.config->'drawdown'->>'defensive')::numeric then 'DEFENSIVE' when drawdown>=(e.config->'drawdown'->>'caution')::numeric then 'CAUTION' else 'NORMAL' end;
  if risk_name='HALTED' then raise exception 'iNeed risk engine halted'; end if;
  stake_multiplier:=coalesce((e.config->'risk_profiles'->risk_name->>'stake_multiplier')::numeric,1); exposure_multiplier:=coalesce((e.config->'risk_profiles'->risk_name->>'exposure_multiplier')::numeric,1); stake_value:=coalesce(s.final_stake,0);
  if stake_value<(e.config->>'minimum_stake')::numeric then raise exception 'iNeed stake below operator minimum'; end if; if stake_value>available then raise exception 'iNeed insufficient available capital'; end if;
  single_cap:=equity*(e.config->>'max_single_bet_pct')::numeric*stake_multiplier; total_cap:=equity*(e.config->>'max_total_exposure_pct')::numeric*exposure_multiplier; match_cap:=equity*(e.config->>'max_match_exposure_pct')::numeric*exposure_multiplier; player_cap:=equity*(e.config->>'max_player_exposure_pct')::numeric*exposure_multiplier; market_cap:=equity*(e.config->>'max_market_exposure_pct')::numeric*exposure_multiplier;
  if stake_value>single_cap+0.0001 then raise exception 'iNeed single-bet exposure limit'; end if; if total_exposure+stake_value>total_cap+0.0001 then raise exception 'iNeed total exposure limit'; end if; if match_exposure+stake_value>match_cap+0.0001 then raise exception 'iNeed match exposure limit'; end if; if player_exposure+stake_value>player_cap+0.0001 then raise exception 'iNeed player correlation limit'; end if; if market_exposure+stake_value>market_cap+0.0001 then raise exception 'iNeed market concentration limit'; end if;
  insert into public.ineed_shadow_bets(experiment_id,signal_id,match_id,market,selection,status,stake,odds,potential_payout,bankroll_before,placement_snapshot)
  values(e.id,s.id,s.match_id,s.market,s.selection,'PENDING',stake_value,s.odds,nullif((s.current_snapshot->>'potential_payout')::numeric,0),equity,s.current_snapshot) returning * into bet_row;
  insert into public.ineed_bankroll_ledger(experiment_id,entry_type,amount,source,source_key,bet_id,bankroll_before,bankroll_after)
  values(e.id,'STAKE_RESERVED',-stake_value,'ineed_shadow_bet','reserve:'||bet_row.id,bet_row.id,available,available-stake_value);
  update public.ineed_signals set status='PENDING',updated_at=now() where id=s.id;
  return jsonb_build_object('status','PLACED','bet_id',bet_row.id,'stake',stake_value,'available_after',available-stake_value,'risk_state',risk_name,'drawdown',drawdown);
end $$;
revoke all on function public.ineed_system_place_bet(uuid) from public,anon,authenticated;
grant execute on function public.ineed_system_place_bet(uuid) to service_role;
