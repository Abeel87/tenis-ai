-- Training archive physical-object health probe and finalization hardening.
-- Additive only: this does not change model math, training, runtime delivery,
-- PLAYABLE, Symphony, Neuron, Player DNA, Surface Elo or iNeed$.

create or replace function public.training_archive_probe_objects(
  p_sha256 text[]
)
returns table (
  sha256 text,
  storage_path text,
  expected_size bigint,
  physical_size bigint,
  present boolean,
  size_matches boolean
)
language sql
security definer
set search_path = pg_catalog, public, storage
as $$
  select
    o.sha256,
    o.storage_path,
    o.size_bytes as expected_size,
    case
      when s.id is null then null::bigint
      else coalesce((s.metadata ->> 'size')::bigint, -1)
    end as physical_size,
    s.id is not null as present,
    s.id is not null
      and coalesce((s.metadata ->> 'size')::bigint, -1) = o.size_bytes as size_matches
  from public.training_archive_objects o
  left join storage.objects s
    on s.bucket_id = 'tenis-ai-training-archive-private'
   and s.name = o.storage_path
  where o.sha256 = any(p_sha256);
$$;

revoke all on function public.training_archive_probe_objects(text[])
  from public, anon, authenticated;
grant execute on function public.training_archive_probe_objects(text[])
  to service_role;

create or replace function public.training_archive_finalize_manifest(
  p_manifest_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public, storage
as $$
declare
  m public.training_archive_manifests%rowtype;
  v_files bigint;
  v_bytes bigint;
  v_unique_objects bigint;
  v_unique_bytes bigint;
  v_unverified bigint;
  v_missing bigint;
  v_size_mismatch bigint;
begin
  select * into m
  from public.training_archive_manifests
  where manifest_id = p_manifest_id
  for update;

  if not found then
    return false;
  end if;

  if m.status = 'complete' then
    return true;
  end if;

  select count(*), coalesce(sum(e.size_bytes), 0), count(distinct e.object_sha256)
    into v_files, v_bytes, v_unique_objects
  from public.training_archive_entries e
  where e.manifest_id = p_manifest_id;

  select
    coalesce(sum(o.size_bytes), 0),
    count(*) filter (where o.verified_at is null),
    count(*) filter (where s.id is null),
    count(*) filter (
      where s.id is not null
        and coalesce((s.metadata ->> 'size')::bigint, -1) <> o.size_bytes
    )
    into v_unique_bytes, v_unverified, v_missing, v_size_mismatch
  from public.training_archive_objects o
  left join storage.objects s
    on s.bucket_id = 'tenis-ai-training-archive-private'
   and s.name = o.storage_path
  where o.sha256 in (
    select distinct e.object_sha256
    from public.training_archive_entries e
    where e.manifest_id = p_manifest_id
  );

  if v_files <> m.expected_files
     or v_bytes <> m.expected_bytes
     or v_unique_objects <> m.expected_unique_objects
     or v_unique_bytes <> m.expected_unique_bytes
     or v_unverified <> 0
     or v_missing <> 0
     or v_size_mismatch <> 0 then
    return false;
  end if;

  update public.training_archive_manifests
  set status = 'complete', completed_at = now()
  where manifest_id = p_manifest_id;

  return true;
end;
$$;

revoke all on function public.training_archive_finalize_manifest(uuid)
  from public, anon, authenticated;
grant execute on function public.training_archive_finalize_manifest(uuid)
  to service_role;
