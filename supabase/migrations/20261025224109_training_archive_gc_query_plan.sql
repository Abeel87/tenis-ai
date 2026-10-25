-- Remove planner-sensitive full entry scans from the existing GC owners.
-- With 1.1M entries, the non-complete branch scanned every entry even though
-- its 112 terminal manifests had no entries. Prepare also built a global
-- entry anti-join before finding blocked manifests.
-- OFFSET 0 preserves indexed, parameterized lookups; it does not limit rows.
-- All eligibility predicates, 168h default, latest-two/pins, resume/audit,
-- physical-size checks, ACLs and 30s timeouts remain unchanged.
-- No table rows or Storage objects are changed by this migration.

CREATE OR REPLACE FUNCTION public.training_archive_retention_observe(p_keep_latest integer DEFAULT 2, p_grace_hours integer DEFAULT 168)
 RETURNS TABLE(observation_id bigint, observed_at timestamp with time zone, keep_latest integer, grace_hours integer, complete_manifests bigint, active_pins bigint, pinned_manifests bigint, retained_complete_manifests bigint, expirable_complete_manifests bigint, current_candidate_objects bigint, current_candidate_bytes bigint, grace_ready_objects bigint, grace_ready_bytes bigint, deactivated_candidates bigint)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
 SET statement_timeout TO '30s'
AS $function$
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
    from retained_complete r
    cross join lateral (
      select e.object_sha256
      from public.training_archive_entries e
      where e.manifest_id = r.manifest_id
      offset 0
    ) e

    union

    select distinct e.object_sha256
    from public.training_archive_manifests m
    -- Prevent empty terminal manifests from choosing a full entry-table scan.
    cross join lateral (
      select e.object_sha256
      from public.training_archive_entries e
      where e.manifest_id = m.manifest_id
      offset 0
    ) e
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

  insert into public.training_archive_retention_audit as audit (
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
  ) returning audit.observation_id into v_observation_id;

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
$function$
;

CREATE OR REPLACE FUNCTION public.training_archive_gc_prepare(p_archive_run_id bigint, p_archive_run_attempt integer, p_source_sha text, p_keep_latest integer DEFAULT 2, p_grace_hours integer DEFAULT 168, p_batch_limit integer DEFAULT 100)
 RETURNS TABLE(apply_id bigint, status text, expired_manifests integer, planned_objects integer, planned_bytes bigint, deleted_objects integer, deleted_bytes bigint, skipped_objects integer)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public', 'storage'
 SET statement_timeout TO '30s'
AS $function$
declare
  v_now timestamptz := now();
  v_apply_id bigint;
  v_expire_ids uuid[] := array[]::uuid[];
  v_expired integer := 0;
  v_planned integer := 0;
  v_planned_bytes bigint := 0;
  v_status text := 'prepared';
begin
  if p_archive_run_id <= 0 or p_archive_run_attempt <= 0 then
    raise exception 'archive run identity must be positive';
  end if;
  if p_source_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'source sha must be a lowercase 40-character sha';
  end if;
  if p_keep_latest < 2 or p_keep_latest > 100 then
    raise exception 'p_keep_latest must be between 2 and 100';
  end if;
  if p_grace_hours < 24 or p_grace_hours > 720 then
    raise exception 'p_grace_hours must be between 24 and 720';
  end if;
  if p_batch_limit < 1 or p_batch_limit > 500 then
    raise exception 'p_batch_limit must be between 1 and 500';
  end if;

  perform pg_advisory_xact_lock(hashtext('training_archive_gc_apply'));

  select a.apply_id
    into v_apply_id
  from public.training_archive_gc_apply_audit a
  where a.status in ('prepared', 'partial')
    and exists (
      select 1
      from public.training_archive_gc_apply_objects ao
      where ao.apply_id = a.apply_id
        and ao.deleted_at is null
        and ao.skipped_at is null
    )
  order by a.apply_id
  limit 1;

  if v_apply_id is not null then
    return query
    select a.apply_id, a.status, a.expired_manifests, a.planned_objects,
           a.planned_bytes, a.deleted_objects, a.deleted_bytes, a.skipped_objects
    from public.training_archive_gc_apply_audit a
    where a.apply_id = v_apply_id;
    return;
  end if;

  perform public.training_archive_retention_observe(p_keep_latest, p_grace_hours);

  with ranked_complete as (
    select m.manifest_id,
           row_number() over (order by m.created_at desc, m.manifest_id desc) as rn
    from public.training_archive_manifests m
    where m.status = 'complete'
  ),
  retained_complete as (
    select r.manifest_id from ranked_complete r where r.rn <= p_keep_latest
    union
    select p.manifest_id
    from public.training_archive_manifest_pins p
    join public.training_archive_manifests m
      on m.manifest_id = p.manifest_id and m.status = 'complete'
    where p.released_at is null
  ),
  retained_references as (
    select distinct e.object_sha256
    from retained_complete r
    cross join lateral (
      select e.object_sha256
      from public.training_archive_entries e
      where e.manifest_id = r.manifest_id
      offset 0
    ) e
    union
    select distinct e.object_sha256
    from public.training_archive_manifests m
    -- Prevent empty terminal manifests from choosing a full entry-table scan.
    cross join lateral (
      select e.object_sha256
      from public.training_archive_entries e
      where e.manifest_id = m.manifest_id
      offset 0
    ) e
    where m.status <> 'complete'
  ),
  expirable as (
    select r.manifest_id
    from ranked_complete r
    where not exists (select 1 from retained_complete k where k.manifest_id = r.manifest_id)
  ),
  -- Entry -> object FK guarantees this object-first complement is equivalent
  -- to the former entry-first anti-join, including shared and absent Storage.
  blocking_objects as materialized (
    select o.sha256
    from public.training_archive_objects o
    where not exists (
      select 1 from retained_references rr where rr.object_sha256 = o.sha256
    )
    and not exists (
      select 1
      from public.training_archive_gc_candidates g
      join storage.objects s
        on s.bucket_id = 'tenis-ai-training-archive-private'
       and s.name = o.storage_path
       and coalesce((s.metadata ->> 'size')::bigint, -1) = o.size_bytes
      where g.sha256 = o.sha256
        and g.current_eligible
        and g.grace_until <= v_now
    )
  ),
  blocked_manifests as materialized (
    select distinct e.manifest_id
    from blocking_objects b
    cross join lateral (
      select e.manifest_id
      from public.training_archive_entries e
      where e.object_sha256 = b.sha256
      offset 0
    ) e
  ),
  ready_manifests as (
    select x.manifest_id
    from expirable x
    where not exists (
      select 1 from blocked_manifests b where b.manifest_id = x.manifest_id
    )
  )
  select coalesce(array_agg(r.manifest_id order by r.manifest_id), array[]::uuid[])
    into v_expire_ids
  from ready_manifests r;

  v_expired := coalesce(array_length(v_expire_ids, 1), 0);

  if v_expired > 0 then
    update public.training_archive_manifests m
       set status = 'expired', expired_at = v_now
     where m.manifest_id = any(v_expire_ids)
       and m.status = 'complete';

    delete from public.training_archive_entries e
     where e.manifest_id = any(v_expire_ids);
  end if;

  insert into public.training_archive_gc_apply_audit (
    archive_run_id, archive_run_attempt, source_sha, keep_latest, grace_hours,
    status, expired_manifests
  ) values (
    p_archive_run_id, p_archive_run_attempt, p_source_sha, p_keep_latest,
    p_grace_hours, 'prepared', v_expired
  )
  returning training_archive_gc_apply_audit.apply_id into v_apply_id;

  insert into public.training_archive_gc_apply_objects (
    apply_id, sha256, storage_path, size_bytes
  )
  select v_apply_id, o.sha256, o.storage_path, o.size_bytes
  from public.training_archive_objects o
  join public.training_archive_gc_candidates g on g.sha256 = o.sha256
  join storage.objects s
    on s.bucket_id = 'tenis-ai-training-archive-private'
   and s.name = o.storage_path
   and coalesce((s.metadata ->> 'size')::bigint, -1) = o.size_bytes
  where g.current_eligible
    and g.grace_until <= v_now
    and not exists (
      select 1 from public.training_archive_entries e where e.object_sha256 = o.sha256
    )
  order by o.sha256
  limit p_batch_limit;

  get diagnostics v_planned = row_count;
  select coalesce(sum(ao.size_bytes), 0)
    into v_planned_bytes
  from public.training_archive_gc_apply_objects ao
  where ao.apply_id = v_apply_id;

  if v_planned = 0 then
    v_status := case when v_expired = 0 then 'noop' else 'complete' end;
    update public.training_archive_gc_apply_audit a
       set status = v_status,
           planned_objects = 0,
           planned_bytes = 0,
           finished_at = v_now
     where a.apply_id = v_apply_id;
  else
    update public.training_archive_gc_apply_audit a
       set planned_objects = v_planned,
           planned_bytes = v_planned_bytes
     where a.apply_id = v_apply_id;
  end if;

  return query
  select a.apply_id, a.status, a.expired_manifests, a.planned_objects,
         a.planned_bytes, a.deleted_objects, a.deleted_bytes, a.skipped_objects
  from public.training_archive_gc_apply_audit a
  where a.apply_id = v_apply_id;
end;
$function$
;

revoke all on function public.training_archive_retention_observe(integer, integer)
  from public, anon, authenticated;
grant execute on function public.training_archive_retention_observe(integer, integer)
  to service_role;
revoke all on function public.training_archive_gc_prepare(bigint, integer, text, integer, integer, integer)
  from public, anon, authenticated;
grant execute on function public.training_archive_gc_prepare(bigint, integer, text, integer, integer, integer)
  to service_role;

