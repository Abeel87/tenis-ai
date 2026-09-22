-- Destructive apply phase for durable training-archive retention.
-- This remains infrastructure-only: no model math, training, probability,
-- Player DNA, Surface Elo, Symphony, Neuron, PLAYABLE, settlement or iNeed$ changes.

alter table public.training_archive_manifests
  add column if not exists expired_at timestamptz;

alter table public.training_archive_manifests
  drop constraint if exists training_archive_manifests_status_check;
alter table public.training_archive_manifests
  add constraint training_archive_manifests_status_check
  check (status in ('staged', 'complete', 'expired'));

alter table public.training_archive_manifests
  drop constraint if exists training_archive_manifests_expired_state_check;
alter table public.training_archive_manifests
  add constraint training_archive_manifests_expired_state_check
  check ((status = 'expired') = (expired_at is not null)) not valid;
alter table public.training_archive_manifests
  validate constraint training_archive_manifests_expired_state_check;

create table if not exists public.training_archive_gc_apply_audit (
  apply_id bigint generated always as identity primary key,
  archive_run_id bigint not null check (archive_run_id > 0),
  archive_run_attempt integer not null check (archive_run_attempt > 0),
  source_sha text not null check (source_sha ~ '^[0-9a-f]{40}$'),
  keep_latest integer not null check (keep_latest between 2 and 100),
  grace_hours integer not null check (grace_hours between 24 and 720),
  status text not null check (status in ('prepared', 'partial', 'complete', 'noop')),
  expired_manifests integer not null default 0 check (expired_manifests >= 0),
  planned_objects integer not null default 0 check (planned_objects >= 0),
  planned_bytes bigint not null default 0 check (planned_bytes >= 0),
  deleted_objects integer not null default 0 check (deleted_objects >= 0),
  deleted_bytes bigint not null default 0 check (deleted_bytes >= 0),
  skipped_objects integer not null default 0 check (skipped_objects >= 0),
  created_at timestamptz not null default now(),
  finished_at timestamptz,
  unique (archive_run_id, archive_run_attempt)
);

create table if not exists public.training_archive_gc_apply_objects (
  apply_id bigint not null references public.training_archive_gc_apply_audit(apply_id) on delete restrict,
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  storage_path text not null,
  size_bytes bigint not null check (size_bytes >= 0 and size_bytes <= 47185920),
  remove_started_at timestamptz,
  deleted_at timestamptz,
  skipped_at timestamptz,
  skip_reason text,
  primary key (apply_id, sha256),
  constraint training_archive_gc_apply_objects_terminal_check
    check (not (deleted_at is not null and skipped_at is not null)),
  constraint training_archive_gc_apply_objects_skip_reason_check
    check ((skipped_at is null and skip_reason is null) or (skipped_at is not null and skip_reason in ('referenced', 'not_ready')))
);

create index if not exists training_archive_gc_apply_objects_pending_idx
  on public.training_archive_gc_apply_objects(apply_id, sha256)
  where deleted_at is null and skipped_at is null;

alter table public.training_archive_gc_apply_audit enable row level security;
alter table public.training_archive_gc_apply_objects enable row level security;
revoke all on table public.training_archive_gc_apply_audit from public, anon, authenticated;
revoke all on table public.training_archive_gc_apply_objects from public, anon, authenticated;
revoke all on table public.training_archive_gc_apply_audit from service_role;
revoke all on table public.training_archive_gc_apply_objects from service_role;
grant select on table public.training_archive_gc_apply_audit to service_role;
grant select on table public.training_archive_gc_apply_objects to service_role;

create or replace function public.training_archive_gc_prepare(
  p_archive_run_id bigint,
  p_archive_run_attempt integer,
  p_source_sha text,
  p_keep_latest integer default 2,
  p_grace_hours integer default 168,
  p_batch_limit integer default 100
)
returns table (
  apply_id bigint,
  status text,
  expired_manifests integer,
  planned_objects integer,
  planned_bytes bigint,
  deleted_objects integer,
  deleted_bytes bigint,
  skipped_objects integer
)
language plpgsql
security definer
set search_path = pg_catalog, public, storage
as $$
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

  -- Resume an unfinished destructive batch before creating another one.
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

  -- Refresh candidate eligibility and the seven-day grace clock first.
  perform public.training_archive_retention_observe(p_keep_latest, p_grace_hours);

  -- A manifest may expire only when every object that is not protected by the
  -- retained rolling window / active pins / in-flight manifests has completed
  -- grace and still exists physically at the exact recorded size.
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
    from public.training_archive_entries e
    where e.manifest_id in (select r.manifest_id from retained_complete r)
    union
    select distinct e.object_sha256
    from public.training_archive_entries e
    join public.training_archive_manifests m on m.manifest_id = e.manifest_id
    where m.status <> 'complete'
  ),
  expirable as (
    select r.manifest_id
    from ranked_complete r
    where not exists (select 1 from retained_complete k where k.manifest_id = r.manifest_id)
  ),
  ready_manifests as (
    select x.manifest_id
    from expirable x
    where not exists (
      select 1
      from public.training_archive_entries e
      left join retained_references rr on rr.object_sha256 = e.object_sha256
      where e.manifest_id = x.manifest_id
        and rr.object_sha256 is null
        and not exists (
          select 1
          from public.training_archive_gc_candidates g
          join public.training_archive_objects o on o.sha256 = g.sha256
          join storage.objects s
            on s.bucket_id = 'tenis-ai-training-archive-private'
           and s.name = o.storage_path
           and coalesce((s.metadata ->> 'size')::bigint, -1) = o.size_bytes
          where g.sha256 = e.object_sha256
            and g.current_eligible
            and g.grace_until <= v_now
        )
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
$$;

create or replace function public.training_archive_gc_claim_object(
  p_apply_id bigint,
  p_sha256 text
)
returns table (state text, storage_path text, size_bytes bigint)
language plpgsql
security definer
set search_path = pg_catalog, public, storage
as $$
declare
  ao public.training_archive_gc_apply_objects%rowtype;
  o public.training_archive_objects%rowtype;
  g public.training_archive_gc_candidates%rowtype;
  v_storage_size bigint;
begin
  perform pg_advisory_xact_lock(hashtext('training_archive_gc_apply'));

  select * into ao
  from public.training_archive_gc_apply_objects x
  where x.apply_id = p_apply_id and x.sha256 = p_sha256
  for update;

  if not found then
    return query select 'unknown'::text, null::text, null::bigint;
    return;
  end if;
  if ao.deleted_at is not null or ao.skipped_at is not null then
    return query select 'terminal'::text, ao.storage_path, ao.size_bytes;
    return;
  end if;
  if exists (select 1 from public.training_archive_entries e where e.object_sha256 = p_sha256) then
    return query select 'referenced'::text, ao.storage_path, ao.size_bytes;
    return;
  end if;

  select * into g from public.training_archive_gc_candidates c where c.sha256 = p_sha256;
  if not found or not g.current_eligible or g.grace_until > now() then
    return query select 'not_ready'::text, ao.storage_path, ao.size_bytes;
    return;
  end if;

  select * into o from public.training_archive_objects x where x.sha256 = p_sha256;
  if not found or o.storage_path <> ao.storage_path or o.size_bytes <> ao.size_bytes then
    return query select 'metadata_mismatch'::text, ao.storage_path, ao.size_bytes;
    return;
  end if;

  select (s.metadata ->> 'size')::bigint
    into v_storage_size
  from storage.objects s
  where s.bucket_id = 'tenis-ai-training-archive-private'
    and s.name = ao.storage_path;

  if not found then
    if ao.remove_started_at is not null then
      return query select 'resume_finalize'::text, ao.storage_path, ao.size_bytes;
    end if;
    return query select 'missing_unexpected'::text, ao.storage_path, ao.size_bytes;
    return;
  end if;
  if coalesce(v_storage_size, -1) <> ao.size_bytes then
    return query select 'size_mismatch'::text, ao.storage_path, ao.size_bytes;
    return;
  end if;

  update public.training_archive_gc_apply_objects x
     set remove_started_at = coalesce(x.remove_started_at, now())
   where x.apply_id = p_apply_id and x.sha256 = p_sha256;

  return query select 'delete'::text, ao.storage_path, ao.size_bytes;
end;
$$;

create or replace function public.training_archive_gc_finalize_object(
  p_apply_id bigint,
  p_sha256 text
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public, storage
as $$
declare
  ao public.training_archive_gc_apply_objects%rowtype;
  v_deleted integer;
begin
  perform pg_advisory_xact_lock(hashtext('training_archive_gc_apply'));

  select * into ao
  from public.training_archive_gc_apply_objects x
  where x.apply_id = p_apply_id and x.sha256 = p_sha256
  for update;

  if not found then return false; end if;
  if ao.deleted_at is not null then return true; end if;
  if ao.skipped_at is not null or ao.remove_started_at is null then return false; end if;
  if exists (select 1 from public.training_archive_entries e where e.object_sha256 = p_sha256) then return false; end if;
  if not exists (
    select 1 from public.training_archive_gc_candidates g
    where g.sha256 = p_sha256 and g.current_eligible and g.grace_until <= now()
  ) then return false; end if;
  if exists (
    select 1 from storage.objects s
    where s.bucket_id = 'tenis-ai-training-archive-private' and s.name = ao.storage_path
  ) then return false; end if;

  delete from public.training_archive_gc_candidates g where g.sha256 = p_sha256;
  delete from public.training_archive_objects o
   where o.sha256 = p_sha256
     and not exists (select 1 from public.training_archive_entries e where e.object_sha256 = o.sha256);
  get diagnostics v_deleted = row_count;
  if v_deleted <> 1 then
    raise exception 'training archive GC object metadata did not delete exactly one row';
  end if;

  update public.training_archive_gc_apply_objects x
     set deleted_at = now()
   where x.apply_id = p_apply_id and x.sha256 = p_sha256;

  update public.training_archive_gc_apply_audit a
     set deleted_objects = deleted_objects + 1,
         deleted_bytes = deleted_bytes + ao.size_bytes
   where a.apply_id = p_apply_id;

  return true;
end;
$$;

create or replace function public.training_archive_gc_skip_object(
  p_apply_id bigint,
  p_sha256 text,
  p_reason text
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  ao public.training_archive_gc_apply_objects%rowtype;
  v_allowed boolean := false;
begin
  if p_reason not in ('referenced', 'not_ready') then return false; end if;
  perform pg_advisory_xact_lock(hashtext('training_archive_gc_apply'));
  select * into ao
  from public.training_archive_gc_apply_objects x
  where x.apply_id = p_apply_id and x.sha256 = p_sha256
  for update;
  if not found then return false; end if;
  if ao.deleted_at is not null or ao.skipped_at is not null then return true; end if;

  if p_reason = 'referenced' then
    v_allowed := exists (select 1 from public.training_archive_entries e where e.object_sha256 = p_sha256);
  else
    v_allowed := not exists (
      select 1 from public.training_archive_gc_candidates g
      where g.sha256 = p_sha256 and g.current_eligible and g.grace_until <= now()
    );
  end if;
  if not v_allowed then return false; end if;

  update public.training_archive_gc_apply_objects x
     set skipped_at = now(), skip_reason = p_reason
   where x.apply_id = p_apply_id and x.sha256 = p_sha256;
  update public.training_archive_gc_apply_audit a
     set skipped_objects = skipped_objects + 1
   where a.apply_id = p_apply_id;
  return true;
end;
$$;

create or replace function public.training_archive_gc_finish_apply(
  p_apply_id bigint
)
returns text
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_remaining integer;
  v_status text;
begin
  perform pg_advisory_xact_lock(hashtext('training_archive_gc_apply'));
  select count(*) into v_remaining
  from public.training_archive_gc_apply_objects ao
  where ao.apply_id = p_apply_id
    and ao.deleted_at is null
    and ao.skipped_at is null;

  v_status := case when v_remaining = 0 then 'complete' else 'partial' end;
  update public.training_archive_gc_apply_audit a
     set status = v_status,
         finished_at = case when v_remaining = 0 then now() else a.finished_at end
   where a.apply_id = p_apply_id;
  return v_status;
end;
$$;

revoke all on function public.training_archive_gc_prepare(bigint, integer, text, integer, integer, integer)
  from public, anon, authenticated;
revoke all on function public.training_archive_gc_claim_object(bigint, text)
  from public, anon, authenticated;
revoke all on function public.training_archive_gc_finalize_object(bigint, text)
  from public, anon, authenticated;
revoke all on function public.training_archive_gc_skip_object(bigint, text, text)
  from public, anon, authenticated;
revoke all on function public.training_archive_gc_finish_apply(bigint)
  from public, anon, authenticated;

grant execute on function public.training_archive_gc_prepare(bigint, integer, text, integer, integer, integer)
  to service_role;
grant execute on function public.training_archive_gc_claim_object(bigint, text)
  to service_role;
grant execute on function public.training_archive_gc_finalize_object(bigint, text)
  to service_role;
grant execute on function public.training_archive_gc_skip_object(bigint, text, text)
  to service_role;
grant execute on function public.training_archive_gc_finish_apply(bigint)
  to service_role;
