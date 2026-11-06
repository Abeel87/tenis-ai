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
  -- Stop after the first blocking reference in each expirable manifest.
  -- IS TRUE keeps membership as a hashed scalar subplan instead of a
  -- parameterized join that rereads all references of each blocking object.
  -- SHA256 is NOT NULL; IS TRUE preserves the original anti-join semantics.
  -- PK order plus OFFSET keeps the per-manifest lookup indexable even when
  -- EXISTS estimates that a whole-table scan could find its first row sooner.
  ready_manifests as (
    select x.manifest_id
    from expirable x
    where not exists (
      select 1
      from (
        select e.object_sha256
        from public.training_archive_entries e
        where e.manifest_id = x.manifest_id
        order by e.logical_path
        offset 0
      ) e
      where (e.object_sha256 in (select b.sha256 from blocking_objects b)) is true
      offset 0
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

revoke all on function public.training_archive_gc_prepare(bigint, integer, text, integer, integer, integer)
  from public, anon, authenticated;
grant execute on function public.training_archive_gc_prepare(bigint, integer, text, integer, integer, integer)
  to service_role;
