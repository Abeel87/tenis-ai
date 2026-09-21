-- LOGIC-12: staff-only aggregate exposure summary for the iNeed$ presentation.
-- Keeps the normalized exposure view service-only and exposes no builder row detail.

create or replace function public.ineed_staff_exposure_summary(target_experiment_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  total_exposure numeric(14,4);
  open_units bigint;
  v1_open_units bigint;
  builder_open_units bigint;
begin
  if uid is null or not public.is_staff(uid) then
    raise exception 'iNeed$ exposure summary requires staff access';
  end if;
  if target_experiment_id is null then
    raise exception 'iNeed$ experiment id is required';
  end if;
  if not exists (
    select 1 from public.ineed_experiments e where e.id = target_experiment_id
  ) then
    raise exception 'iNeed$ experiment not found';
  end if;

  select
    coalesce(sum(r.stake),0),
    count(*),
    count(*) filter (where r.economic_unit = 'V1_SINGLE_BET'),
    count(*) filter (where r.economic_unit = 'BET_BUILDER_COMPOSITION')
  into total_exposure, open_units, v1_open_units, builder_open_units
  from public.ineed_open_risk_exposures r
  where r.experiment_id = target_experiment_id;

  return jsonb_build_object(
    'source','SHARED_DB',
    'total_exposure',total_exposure,
    'open_units',open_units,
    'v1_open_units',v1_open_units,
    'builder_open_units',builder_open_units
  );
end $$;

revoke all on function public.ineed_staff_exposure_summary(uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.ineed_staff_exposure_summary(uuid)
  to authenticated;
