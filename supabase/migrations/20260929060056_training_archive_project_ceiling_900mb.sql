-- Allow normal runtime snapshot overlap while keeping a 900 MB project ceiling.
-- Preserve the 300 MB archive cap, SHA dedupe, locks, ACLs and retention.

create or replace function public.training_archive_enforce_budget()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public, storage
as $$
declare
  v_archive_reserved_bytes bigint := 0;
  v_project_physical_bytes bigint := 0;
  v_archive_missing_reserved_bytes bigint := 0;
  v_project_accounted_bytes bigint := 0;
  c_archive_budget_bytes constant bigint := 300000000;
  c_project_archive_write_ceiling_bytes constant bigint := 900000000;
begin
  if new.status <> 'staged' then
    return new;
  end if;

  perform pg_advisory_xact_lock(1339352577, 20260919);

  select coalesce(sum(o.size_bytes), 0)
    into v_archive_reserved_bytes
  from public.training_archive_objects o;

  select coalesce(sum(coalesce((s.metadata ->> 'size')::bigint, 0)), 0)
    into v_project_physical_bytes
  from storage.objects s;

  select coalesce(sum(o.size_bytes), 0)
    into v_archive_missing_reserved_bytes
  from public.training_archive_objects o
  left join storage.objects s
    on s.bucket_id = 'tenis-ai-training-archive-private'
   and s.name = o.storage_path
  where s.id is null;

  v_project_accounted_bytes := v_project_physical_bytes + v_archive_missing_reserved_bytes;

  if v_archive_reserved_bytes > c_archive_budget_bytes then
    raise exception using
      errcode = 'P0001',
      message = format(
        'training archive budget already exceeded: reserved bytes %s > %s',
        v_archive_reserved_bytes,
        c_archive_budget_bytes
      );
  end if;

  if v_project_accounted_bytes > c_project_archive_write_ceiling_bytes then
    raise exception using
      errcode = 'P0001',
      message = format(
        'training archive project storage ceiling already exceeded: accounted bytes %s > %s',
        v_project_accounted_bytes,
        c_project_archive_write_ceiling_bytes
      );
  end if;

  return new;
end;
$$;

create or replace function public.training_archive_enforce_object_budget()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public, storage
as $$
declare
  v_archive_reserved_bytes bigint := 0;
  v_project_physical_bytes bigint := 0;
  v_archive_missing_reserved_bytes bigint := 0;
  v_project_accounted_bytes bigint := 0;
  c_archive_budget_bytes constant bigint := 300000000;
  c_project_archive_write_ceiling_bytes constant bigint := 900000000;
begin
  -- Serialize archive reservations so two publishers cannot independently pass
  -- the same budget snapshot and oversubscribe the shared project quota.
  perform pg_advisory_xact_lock(1339352577, 20260919);

  select coalesce(sum(o.size_bytes), 0)
    into v_archive_reserved_bytes
  from public.training_archive_objects o;

  select coalesce(sum(coalesce((s.metadata ->> 'size')::bigint, 0)), 0)
    into v_project_physical_bytes
  from storage.objects s;

  select coalesce(sum(o.size_bytes), 0)
    into v_archive_missing_reserved_bytes
  from public.training_archive_objects o
  left join storage.objects s
    on s.bucket_id = 'tenis-ai-training-archive-private'
   and s.name = o.storage_path
  where s.id is null;

  v_project_accounted_bytes := v_project_physical_bytes + v_archive_missing_reserved_bytes;

  if v_archive_reserved_bytes > c_archive_budget_bytes then
    raise exception using
      errcode = 'P0001',
      message = format(
        'training archive budget exceeded: reserved bytes %s > %s',
        v_archive_reserved_bytes,
        c_archive_budget_bytes
      );
  end if;

  if v_project_accounted_bytes > c_project_archive_write_ceiling_bytes then
    raise exception using
      errcode = 'P0001',
      message = format(
        'training archive project storage ceiling exceeded: accounted bytes %s > %s',
        v_project_accounted_bytes,
        c_project_archive_write_ceiling_bytes
      );
  end if;

  return null;
end;
$$;

revoke all on function public.training_archive_enforce_budget()
  from public, anon, authenticated;
grant execute on function public.training_archive_enforce_budget()
  to service_role;

revoke all on function public.training_archive_enforce_object_budget()
  from public, anon, authenticated;
grant execute on function public.training_archive_enforce_object_budget()
  to service_role;

