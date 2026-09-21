-- LOGIC-12: make experiment rollover see the normalized shared open exposure source.
-- Repository migration only; no builder writer, settlement, or deployment.

create or replace function public.ineed_admin_start_experiment(next_name text default null, config_override jsonb default null)
returns uuid language plpgsql security definer set search_path='public','auth' as $$
declare uid uuid:=auth.uid(); previous public.ineed_experiments%rowtype; cfg jsonb; start_amount numeric(14,4); cfg_version text; new_id uuid; available numeric(14,4); exposure numeric(14,4);
begin
  if uid is null or not public.is_admin(uid) then raise exception 'Tylko administrator może rozpocząć eksperyment iNeed$.'; end if;
  select * into previous from public.ineed_experiments where status='ACTIVE' for update;
  if found then
    select coalesce((select bankroll_after from public.ineed_bankroll_ledger where experiment_id=previous.id order by created_at desc,id desc limit 1),0) into available;
    select coalesce(sum(stake),0) into exposure from public.ineed_open_risk_exposures where experiment_id=previous.id;
    if exposure>0 then raise exception 'Nie można rozpocząć nowego eksperymentu, gdy poprzedni ma otwarte zakłady.'; end if;
    update public.ineed_experiments set status='COMPLETED',ended_at=now(),final_bankroll=available where id=previous.id;
    cfg:=coalesce(config_override,previous.config);
  else cfg:=config_override; end if;
  if cfg is null then raise exception 'Brak konfiguracji iNeed$.'; end if;
  if coalesce(cfg->>'operator','')<>'superbet.pl' or coalesce(cfg->>'mode','')<>'SHADOW' then raise exception 'V1 obsługuje wyłącznie superbet.pl / SHADOW'; end if;
  start_amount:=(cfg->>'starting_bankroll')::numeric; cfg_version:=coalesce(cfg->>'version','ineed-v1');
  insert into public.ineed_experiments(name,operator,mode,currency,starting_bankroll,config,config_version,status,created_by)
  values(coalesce(nullif(trim(next_name),''),'ROAD TO 1,000,000 — TEST #'||(coalesce((select max(experiment_no) from public.ineed_experiments),0)+1)::text),'superbet.pl','SHADOW','PLN',start_amount,cfg,cfg_version,'ACTIVE',uid) returning id into new_id;
  insert into public.ineed_bankroll_ledger(experiment_id,entry_type,amount,source,source_key,bankroll_before,bankroll_after)
  values(new_id,'INITIAL_DEPOSIT',start_amount,'experiment_start','initial:'||new_id,0,start_amount);
  insert into public.ineed_runtime_health(experiment_id,status,detail) values(new_id,'NEVER_RUN','{}');
  return new_id;
end $$;

grant execute on function public.ineed_admin_start_experiment(text,jsonb) to authenticated;
