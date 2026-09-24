-- Failed archive publications used to remain `staged` forever. Retention
-- deliberately protects every staged reference, so these partial manifests
-- could pin old objects indefinitely and prevent the 250 MB budget from
-- recovering. Add an explicit terminal state and a bounded stale reaper.
--
-- Abandonment never deletes a physical object. It only removes the incomplete
-- manifest's partial entries; the normal observer then starts a fresh 168-hour
-- eligibility clock before the existing GC may consider any object.

alter table public.training_archive_manifests
  add column if not exists abandoned_at timestamptz;

alter table public.training_archive_manifests
  drop constraint if exists training_archive_manifests_status_check;

alter table public.training_archive_manifests
  add constraint training_archive_manifests_status_check
  check (status in ('staged', 'complete', 'expired', 'abandoned'));

create or replace function public.training_archive_abandon_stale_manifests(
  p_stale_hours integer default 24
)
returns bigint
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_now timestamptz := clock_timestamp();
  v_ids uuid[] := array[]::uuid[];
  v_count bigint := 0;
begin
  if p_stale_hours < 1 or p_stale_hours > 168 then
    raise exception 'p_stale_hours must be between 1 and 168';
  end if;

  perform pg_advisory_xact_lock(hashtext('training_archive_staged_lifecycle'));

  select coalesce(array_agg(m.manifest_id order by m.manifest_id), array[]::uuid[])
    into v_ids
  from public.training_archive_manifests m
  where m.status = 'staged'
    and m.created_at <= v_now - make_interval(hours => p_stale_hours);

  v_count := coalesce(array_length(v_ids, 1), 0);
  if v_count = 0 then
    return 0;
  end if;

  update public.training_archive_manifests m
     set status = 'abandoned', abandoned_at = v_now
   where m.manifest_id = any(v_ids)
     and m.status = 'staged';

  -- Entries of an incomplete manifest are not durable archive provenance.
  -- Removing them only releases references; object deletion remains governed
  -- by the existing observer, 168-hour grace, latest-two and pin checks.
  delete from public.training_archive_entries e
   where e.manifest_id = any(v_ids);

  return v_count;
end;
$$;

revoke all on function public.training_archive_abandon_stale_manifests(integer)
  from public, anon, authenticated;
grant execute on function public.training_archive_abandon_stale_manifests(integer)
  to service_role;

create or replace function public.training_archive_abandon_manifest(
  p_manifest_id uuid,
  p_archive_run_id bigint,
  p_archive_run_attempt integer,
  p_source_sha text
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_status text;
begin
  if p_archive_run_id <= 0 or p_archive_run_attempt <= 0 then
    raise exception 'archive run identity must be positive';
  end if;
  if p_source_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'source sha must be a lowercase 40-character hex value';
  end if;

  perform pg_advisory_xact_lock(hashtext('training_archive_staged_lifecycle'));

  select m.status
    into v_status
  from public.training_archive_manifests m
  where m.manifest_id = p_manifest_id
    and m.archive_run_id = p_archive_run_id
    and m.archive_run_attempt = p_archive_run_attempt
    and m.source_sha = p_source_sha
  for update;

  if not found then
    raise exception 'manifest does not belong to this workflow run';
  end if;
  if v_status = 'complete' then
    raise exception 'a complete manifest cannot be abandoned';
  end if;
  if v_status = 'abandoned' then
    return false;
  end if;
  if v_status <> 'staged' then
    raise exception 'manifest is not staged';
  end if;

  update public.training_archive_manifests
     set status = 'abandoned', abandoned_at = clock_timestamp()
   where manifest_id = p_manifest_id;

  delete from public.training_archive_entries
   where manifest_id = p_manifest_id;

  return true;
end;
$$;

revoke all on function public.training_archive_abandon_manifest(uuid, bigint, integer, text)
  from public, anon, authenticated;
grant execute on function public.training_archive_abandon_manifest(uuid, bigint, integer, text)
  to service_role;
