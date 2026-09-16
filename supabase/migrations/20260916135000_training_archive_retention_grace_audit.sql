-- Grace-period tracking and immutable audit for durable training archive retention.
-- Observation only: this migration does not expire manifests or delete database/Storage objects.
-- It does not change model math, training, Player DNA, Surface Elo, Symphony,
-- Neuron, PLAYABLE, settlement, SHADOW/PROD or iNeed$ calculations.

create table if not exists public.training_archive_gc_candidates (
  sha256 text primary key
    references public.training_archive_objects(sha256) on delete restrict,
  size_bytes bigint not null,
  first_eligible_at timestamptz not null,
  last_eligible_at timestamptz not null,
  grace_until timestamptz not null,
  current_eligible boolean not null default true,
  eligibility_lost_at timestamptz,
  observation_count bigint not null default 1,
  constraint training_archive_gc_candidates_size_check
    check (size_bytes >= 0),
  constraint training_archive_gc_candidates_observation_count_check
    check (observation_count >= 1),
  constraint training_archive_gc_candidates_time_check
    check (last_eligible_at >= first_eligible_at and grace_until >= first_eligible_at),
  constraint training_archive_gc_candidates_state_check
    check (current_eligible = (eligibility_lost_at is null)),
  constraint training_archive_gc_candidates_lost_time_check
    check (eligibility_lost_at is null or eligibility_lost_at >= first_eligible_at)
);

create index if not exists training_archive_gc_candidates_current_grace_idx
  on public.training_archive_gc_candidates(grace_until, sha256)
  where current_eligible;

alter table public.training_archive_gc_candidates enable row level security;
revoke all on table public.training_archive_gc_candidates
  from public, anon, authenticated;
grant select on table public.training_archive_gc_candidates
  to service_role;

create table if not exists public.training_archive_retention_audit (
  observation_id bigint generated always as identity primary key,
  observed_at timestamptz not null default now(),
  keep_latest integer not null,
  grace_hours integer not null,
  complete_manifests bigint not null,
  active_pins bigint not null,
  pinned_manifests bigint not null,
  retained_complete_manifests bigint not null,
  expirable_complete_manifests bigint not null,
  current_candidate_objects bigint not null,
  current_candidate_bytes bigint not null,
  grace_ready_objects bigint not null,
  grace_ready_bytes bigint not null,
  deactivated_candidates bigint not null,
  constraint training_archive_retention_audit_keep_latest_check
    check (keep_latest between 2 and 100),
  constraint training_archive_retention_audit_grace_hours_check
    check (grace_hours between 24 and 720),
  constraint training_archive_retention_audit_nonnegative_check
    check (
      complete_manifests >= 0
      and active_pins >= 0
      and pinned_manifests >= 0
      and retained_complete_manifests >= 0
      and expirable_complete_manifests >= 0
      and current_candidate_objects >= 0
      and current_candidate_bytes >= 0
      and grace_ready_objects >= 0
      and grace_ready_bytes >= 0
      and deactivated_candidates >= 0
    )
);

create index if not exists training_archive_retention_audit_observed_idx
  on public.training_archive_retention_audit(observed_at desc, observation_id desc);

alter table public.training_archive_retention_audit enable row level security;
revoke all on table public.training_archive_retention_audit
  from public, anon, authenticated;
grant select on table public.training_archive_retention_audit
  to service_role;

create or replace function public.training_archive_retention_observe(
  p_keep_latest integer default 2,
  p_grace_hours integer default 168
)
returns table (
  observation_id bigint,
  observed_at timestamptz,
  keep_latest integer,
  grace_hours integer,
  complete_manifests bigint,
  active_pins bigint,
  pinned_manifests bigint,
  retained_complete_manifests bigint,
  expirable_complete_manifests bigint,
  current_candidate_objects bigint,
  current_candidate_bytes bigint,
  grace_ready_objects bigint,
  grace_ready_bytes bigint,
  deactivated_candidates bigint
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_now timestamptz := clock_timestamp();
  v_candidate_shas text[] := '{}'::text[];
  v_complete_manifests bigint := 0;
  v_active_pins bigint := 0;
  v_pinned_manifests bigint := 0;
  v_retained_complete_manifests bigint := 0;
  v_expirable_complete_manifests bigint := 0;
  v_candidate_objects bigint := 0;
  v_candidate_bytes bigint := 0;
  v_grace_ready_objects bigint := 0;
  v_grace_ready_bytes bigint := 0;
  v_deactivated_candidates bigint := 0;
  v_observation_id bigint;
begin
  if p_keep_latest < 2 or p_keep_latest > 100 then
    raise exception 'p_keep_latest must be between 2 and 100';
  end if;
  if p_grace_hours < 24 or p_grace_hours > 720 then
    raise exception 'p_grace_hours must be between 24 and 720';
  end if;

  with ranked_complete as (
    select
      m.manifest_id,
      row_number() over (order by m.created_at desc, m.manifest_id desc) as rn
    from public.training_archive_manifests m
    where m.status = 'complete'
  ),
  active_pin_rows as (
    select p.manifest_id
    from public.training_archive_manifest_pins p
    where p.released_at is null
  ),
  active_pinned_manifests as (
    select distinct p.manifest_id
    from active_pin_rows p
    join public.training_archive_manifests m
      on m.manifest_id = p.manifest_id
     and m.status = 'complete'
  ),
  retained_complete as (
    select r.manifest_id
    from ranked_complete r
    where r.rn <= p_keep_latest
    union
    select p.manifest_id
    from active_pinned_manifests p
  ),
  retained_references as (
    select distinct e.object_sha256
    from public.training_archive_entries e
    join retained_complete r on r.manifest_id = e.manifest_id

    union

    select distinct e.object_sha256
    from public.training_archive_entries e
    join public.training_archive_manifests m on m.manifest_id = e.manifest_id
    where m.status <> 'complete'
  ),
  eventual_candidates as (
    select o.sha256, o.size_bytes
    from public.training_archive_objects o
    left join retained_references r on r.object_sha256 = o.sha256
    where r.object_sha256 is null
  )
  select
    coalesce(array_agg(c.sha256 order by c.sha256), '{}'::text[]),
    count(c.sha256)::bigint,
    coalesce(sum(c.size_bytes), 0)::bigint,
    (select count(*) from ranked_complete)::bigint,
    (select count(*) from active_pin_rows)::bigint,
    (select count(*) from active_pinned_manifests)::bigint,
    (select count(*) from retained_complete)::bigint,
    (
      select count(*)
      from ranked_complete rc
      left join retained_complete r on r.manifest_id = rc.manifest_id
      where r.manifest_id is null
    )::bigint
  into
    v_candidate_shas,
    v_candidate_objects,
    v_candidate_bytes,
    v_complete_manifests,
    v_active_pins,
    v_pinned_manifests,
    v_retained_complete_manifests,
    v_expirable_complete_manifests
  from eventual_candidates c;

  update public.training_archive_gc_candidates g
  set current_eligible = false,
      eligibility_lost_at = v_now
  where g.current_eligible
    and not (g.sha256 = any(v_candidate_shas));
  get diagnostics v_deactivated_candidates = row_count;

  insert into public.training_archive_gc_candidates (
    sha256,
    size_bytes,
    first_eligible_at,
    last_eligible_at,
    grace_until,
    current_eligible,
    eligibility_lost_at,
    observation_count
  )
  select
    o.sha256,
    o.size_bytes,
    v_now,
    v_now,
    v_now + make_interval(hours => p_grace_hours),
    true,
    null,
    1
  from public.training_archive_objects o
  where o.sha256 = any(v_candidate_shas)
  on conflict (sha256) do update
  set size_bytes = excluded.size_bytes,
      first_eligible_at = case
        when public.training_archive_gc_candidates.current_eligible
          then public.training_archive_gc_candidates.first_eligible_at
        else excluded.first_eligible_at
      end,
      last_eligible_at = excluded.last_eligible_at,
      grace_until = case
        when public.training_archive_gc_candidates.current_eligible
          then greatest(
            public.training_archive_gc_candidates.grace_until,
            public.training_archive_gc_candidates.first_eligible_at + make_interval(hours => p_grace_hours)
          )
        else excluded.grace_until
      end,
      current_eligible = true,
      eligibility_lost_at = null,
      observation_count = public.training_archive_gc_candidates.observation_count + 1;

  select
    count(*)::bigint,
    coalesce(sum(g.size_bytes), 0)::bigint
  into v_grace_ready_objects, v_grace_ready_bytes
  from public.training_archive_gc_candidates g
  where g.current_eligible
    and g.grace_until <= v_now;

  insert into public.training_archive_retention_audit (
    observed_at,
    keep_latest,
    grace_hours,
    complete_manifests,
    active_pins,
    pinned_manifests,
    retained_complete_manifests,
    expirable_complete_manifests,
    current_candidate_objects,
    current_candidate_bytes,
    grace_ready_objects,
    grace_ready_bytes,
    deactivated_candidates
  ) values (
    v_now,
    p_keep_latest,
    p_grace_hours,
    v_complete_manifests,
    v_active_pins,
    v_pinned_manifests,
    v_retained_complete_manifests,
    v_expirable_complete_manifests,
    v_candidate_objects,
    v_candidate_bytes,
    v_grace_ready_objects,
    v_grace_ready_bytes,
    v_deactivated_candidates
  ) returning public.training_archive_retention_audit.observation_id
    into v_observation_id;

  return query
  select
    v_observation_id,
    v_now,
    p_keep_latest,
    p_grace_hours,
    v_complete_manifests,
    v_active_pins,
    v_pinned_manifests,
    v_retained_complete_manifests,
    v_expirable_complete_manifests,
    v_candidate_objects,
    v_candidate_bytes,
    v_grace_ready_objects,
    v_grace_ready_bytes,
    v_deactivated_candidates;
end;
$$;

revoke all on function public.training_archive_retention_observe(integer, integer)
  from public, anon, authenticated;
grant execute on function public.training_archive_retention_observe(integer, integer)
  to service_role;
