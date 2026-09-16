-- Durable raw training archive. Additive only: this does not change model math,
-- training, runtime delivery, PLAYABLE, Symphony, Neuron, Player DNA or iNeed$.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'tenis-ai-training-archive-private',
  'tenis-ai-training-archive-private',
  false,
  47185920,
  array['application/gzip', 'application/json']::text[]
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

create table if not exists public.training_archive_manifests (
  manifest_id uuid primary key,
  archive_run_id bigint not null check (archive_run_id > 0),
  archive_run_attempt integer not null check (archive_run_attempt > 0),
  source_sha text not null check (source_sha ~ '^[0-9a-f]{40}$'),
  source_workflow text not null,
  producer_run_id bigint check (producer_run_id is null or producer_run_id > 0),
  producer_head_sha text check (producer_head_sha is null or producer_head_sha ~ '^[0-9a-f]{40}$'),
  source_cache_key text,
  inventory_schema_version integer not null check (inventory_schema_version > 0),
  expected_files integer not null check (expected_files > 0),
  expected_bytes bigint not null check (expected_bytes >= 0),
  expected_unique_objects integer not null check (expected_unique_objects > 0),
  expected_unique_bytes bigint not null check (expected_unique_bytes >= 0),
  status text not null default 'staged' check (status in ('staged', 'complete')),
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (archive_run_id, archive_run_attempt)
);

create table if not exists public.training_archive_objects (
  sha256 text primary key check (sha256 ~ '^[0-9a-f]{64}$'),
  storage_path text not null unique,
  size_bytes bigint not null check (size_bytes >= 0 and size_bytes <= 47185920),
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  check (storage_path = ('objects/' || substr(sha256, 1, 2) || '/' || sha256))
);

create table if not exists public.training_archive_entries (
  manifest_id uuid not null references public.training_archive_manifests(manifest_id) on delete cascade,
  logical_path text not null
    check (
      logical_path ~ '^[A-Za-z0-9_./-]+[.](json|json[.]gz|csv[.]gz)$'
      and position('..' in logical_path) = 0
    ),
  object_sha256 text not null references public.training_archive_objects(sha256),
  object_class text not null check (object_class in ('historical_csv_raw', 'pbp_match_raw', 'pbp_state')),
  provider text not null check (length(provider) between 1 and 80),
  size_bytes bigint not null check (size_bytes >= 0 and size_bytes <= 47185920),
  created_at timestamptz not null default now(),
  primary key (manifest_id, logical_path)
);

create index if not exists training_archive_entries_sha_idx
  on public.training_archive_entries(object_sha256);
create index if not exists training_archive_manifests_status_idx
  on public.training_archive_manifests(status, created_at);

alter table public.training_archive_manifests enable row level security;
alter table public.training_archive_objects enable row level security;
alter table public.training_archive_entries enable row level security;

revoke all on table public.training_archive_manifests from public, anon, authenticated;
revoke all on table public.training_archive_objects from public, anon, authenticated;
revoke all on table public.training_archive_entries from public, anon, authenticated;

grant select, insert, update, delete on table public.training_archive_manifests to service_role;
grant select, insert, update, delete on table public.training_archive_objects to service_role;
grant select, insert, update, delete on table public.training_archive_entries to service_role;

create or replace function public.training_archive_confirm_objects(
  p_manifest_id uuid,
  p_sha256 text[]
)
returns integer
language plpgsql
security definer
set search_path = pg_catalog, public, storage
as $$
declare
  v_requested integer;
  v_present integer;
begin
  select count(distinct e.object_sha256)
    into v_requested
  from public.training_archive_entries e
  where e.manifest_id = p_manifest_id
    and e.object_sha256 = any(p_sha256);

  if v_requested <> coalesce(array_length(p_sha256, 1), 0) then
    return 0;
  end if;

  with present as (
    select distinct o.sha256
    from public.training_archive_objects o
    join public.training_archive_entries e
      on e.object_sha256 = o.sha256
     and e.manifest_id = p_manifest_id
    join storage.objects s
      on s.bucket_id = 'tenis-ai-training-archive-private'
     and s.name = o.storage_path
    where o.sha256 = any(p_sha256)
      and coalesce((s.metadata ->> 'size')::bigint, -1) = o.size_bytes
  ), updated as (
    update public.training_archive_objects o
       set verified_at = coalesce(o.verified_at, now())
      from present p
     where o.sha256 = p.sha256
    returning o.sha256
  )
  select count(*) into v_present from present;

  return v_present;
end;
$$;

revoke all on function public.training_archive_confirm_objects(uuid, text[])
  from public, anon, authenticated;
grant execute on function public.training_archive_confirm_objects(uuid, text[])
  to service_role;

create or replace function public.training_archive_finalize_manifest(
  p_manifest_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  m public.training_archive_manifests%rowtype;
  v_files bigint;
  v_bytes bigint;
  v_unique_objects bigint;
  v_unique_bytes bigint;
  v_unverified bigint;
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

  select coalesce(sum(o.size_bytes), 0),
         count(*) filter (where o.verified_at is null)
    into v_unique_bytes, v_unverified
  from public.training_archive_objects o
  where o.sha256 in (
    select distinct e.object_sha256
    from public.training_archive_entries e
    where e.manifest_id = p_manifest_id
  );

  if v_files <> m.expected_files
     or v_bytes <> m.expected_bytes
     or v_unique_objects <> m.expected_unique_objects
     or v_unique_bytes <> m.expected_unique_bytes
     or v_unverified <> 0 then
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
