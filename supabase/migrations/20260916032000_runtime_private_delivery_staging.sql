-- Private runtime-data staging for the GitHub -> Supabase delivery migration.
-- Additive only: GitHub Pages remains authoritative until the dual-write gate is proven.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'tenis-ai-runtime-private',
  'tenis-ai-runtime-private',
  false,
  104857600,
  array['application/json']::text[]
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

create table if not exists public.runtime_data_generations (
  layer text not null check (layer in ('core', 'market', 'dna', 'neuron')),
  generation uuid not null,
  source_sha text not null check (source_sha ~ '^[0-9a-f]{40}$'),
  source_run_id bigint not null check (source_run_id > 0),
  source_workflow text not null,
  status text not null default 'staged' check (status in ('staged', 'active', 'retired')),
  created_at timestamptz not null default now(),
  activated_at timestamptz,
  primary key (layer, generation)
);

create table if not exists public.runtime_data_objects (
  layer text not null,
  generation uuid not null,
  logical_path text not null
    check (
      logical_path ~ '^data/[A-Za-z0-9_./-]+[.]json$'
      and position('..' in logical_path) = 0
    ),
  storage_path text not null,
  access_tier text not null check (access_tier in ('b', 'c')),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  size_bytes bigint not null check (size_bytes >= 0 and size_bytes <= 104857600),
  created_at timestamptz not null default now(),
  primary key (layer, generation, logical_path),
  foreign key (layer, generation)
    references public.runtime_data_generations(layer, generation)
    on delete cascade,
  check (storage_path = ('objects/' || sha256 || '.json'))
);

create index if not exists runtime_data_objects_sha_idx
  on public.runtime_data_objects(sha256);

create table if not exists public.runtime_data_heads (
  layer text primary key check (layer in ('core', 'market', 'dna', 'neuron')),
  generation uuid not null,
  source_run_id bigint not null check (source_run_id > 0),
  revision bigint not null default 1 check (revision > 0),
  updated_at timestamptz not null default now(),
  foreign key (layer, generation)
    references public.runtime_data_generations(layer, generation)
);

alter table public.runtime_data_generations enable row level security;
alter table public.runtime_data_objects enable row level security;
alter table public.runtime_data_heads enable row level security;

revoke all on table public.runtime_data_generations from public, anon, authenticated;
revoke all on table public.runtime_data_objects from public, anon, authenticated;
revoke all on table public.runtime_data_heads from public, anon, authenticated;

grant select, insert, update, delete on table public.runtime_data_generations to service_role;
grant select, insert, update, delete on table public.runtime_data_objects to service_role;
grant select, insert, update, delete on table public.runtime_data_heads to service_role;

create or replace function public.runtime_data_generation_ready(
  p_layer text,
  p_generation uuid
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_object_count bigint;
  v_missing_count bigint;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'forbidden';
  end if;

  select count(*)
    into v_object_count
  from public.runtime_data_objects
  where layer = p_layer
    and generation = p_generation;

  if v_object_count = 0 then
    return false;
  end if;

  select count(*)
    into v_missing_count
  from public.runtime_data_objects o
  left join storage.objects s
    on s.bucket_id = 'tenis-ai-runtime-private'
   and s.name = o.storage_path
  where o.layer = p_layer
    and o.generation = p_generation
    and s.id is null;

  return v_missing_count = 0;
end;
$$;

revoke all on function public.runtime_data_generation_ready(text, uuid)
  from public, anon, authenticated;
grant execute on function public.runtime_data_generation_ready(text, uuid)
  to service_role;

create or replace function public.runtime_data_activate_generation(
  p_layer text,
  p_generation uuid,
  p_expected_generation uuid default null
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_new_run_id bigint;
  v_new_status text;
  v_current_generation uuid;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'forbidden';
  end if;

  select source_run_id, status
    into v_new_run_id, v_new_status
  from public.runtime_data_generations
  where layer = p_layer
    and generation = p_generation;

  if not found then
    return false;
  end if;

  select generation
    into v_current_generation
  from public.runtime_data_heads
  where layer = p_layer
  for update;

  if found and v_current_generation = p_generation then
    return true;
  end if;

  if v_new_status <> 'staged' then
    return false;
  end if;

  if v_current_generation is null then
    if p_expected_generation is not null then
      return false;
    end if;

    insert into public.runtime_data_heads(layer, generation, source_run_id, revision, updated_at)
    values (p_layer, p_generation, v_new_run_id, 1, now());
  else
    if v_current_generation is distinct from p_expected_generation then
      return false;
    end if;

    update public.runtime_data_generations
    set status = 'retired'
    where layer = p_layer
      and generation = v_current_generation
      and status = 'active';

    update public.runtime_data_heads
    set generation = p_generation,
        source_run_id = v_new_run_id,
        revision = revision + 1,
        updated_at = now()
    where layer = p_layer;
  end if;

  update public.runtime_data_generations
  set status = 'active',
      activated_at = now()
  where layer = p_layer
    and generation = p_generation;

  return true;
end;
$$;

revoke all on function public.runtime_data_activate_generation(text, uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.runtime_data_activate_generation(text, uuid, uuid)
  to service_role;
