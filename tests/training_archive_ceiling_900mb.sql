begin;
create temporary table archive_objects(size_bytes bigint, storage_path text);
create temporary table storage_objects(id int, bucket_id text, name text, metadata jsonb);
create temporary table archive_manifests(status text);
-- Allow normal runtime snapshot overlap while keeping a 900 MB project ceiling.
-- Preserve the 300 MB archive cap, SHA dedupe, locks, ACLs and retention.

create or replace function pg_temp.training_archive_enforce_budget()
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
  from pg_temp.archive_objects o;

  select coalesce(sum(coalesce((s.metadata ->> 'size')::bigint, 0)), 0)
    into v_project_physical_bytes
  from pg_temp.storage_objects s;

  select coalesce(sum(o.size_bytes), 0)
    into v_archive_missing_reserved_bytes
  from pg_temp.archive_objects o
  left join pg_temp.storage_objects s
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

create or replace function pg_temp.training_archive_enforce_object_budget()
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
  from pg_temp.archive_objects o;

  select coalesce(sum(coalesce((s.metadata ->> 'size')::bigint, 0)), 0)
    into v_project_physical_bytes
  from pg_temp.storage_objects s;

  select coalesce(sum(o.size_bytes), 0)
    into v_archive_missing_reserved_bytes
  from pg_temp.archive_objects o
  left join pg_temp.storage_objects s
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


insert into archive_objects values(287542749,'fixture');
insert into storage_objects values(1,'tenis-ai-training-archive-private','fixture','{"size":287542749}'),(2,'runtime','snapshot','{"size":517623204}');
create trigger test_manifest before insert on archive_manifests for each row execute function pg_temp.training_archive_enforce_budget();
create trigger test_object after insert on archive_objects for each statement execute function pg_temp.training_archive_enforce_object_budget();
insert into archive_manifests values('staged');
do $test$ begin
  update storage_objects set metadata='{"size":620000000}' where id=2;
  begin
    insert into archive_manifests values('staged');
    raise exception 'TEST FAILED: project overflow accepted' using errcode='P9999';
  exception when sqlstate 'P0001' then null;
  end;
  update storage_objects set metadata='{"size":517623204}' where id=2;
  begin
    insert into archive_objects values(13000000,'over-budget');
    raise exception 'TEST FAILED: archive overflow accepted' using errcode='P9999';
  exception when sqlstate 'P0001' then null;
  end;
end $test$;
select 'PASS: 805165953 accepted; >900MB project and >300MB archive rejected' as result;
rollback;
