-- Reference-aware retention metadata and GC preview for the durable training archive.
-- Preview only: this migration does not expire manifests or delete database/Storage objects.
-- It does not change model math, training, Player DNA, Surface Elo, Symphony,
-- Neuron, PLAYABLE, settlement, SHADOW/PROD or iNeed$ calculations.

create table if not exists public.training_archive_manifest_pins (
  pin_key text primary key,
  manifest_id uuid not null references public.training_archive_manifests(manifest_id) on delete restrict,
  reason text,
  created_at timestamptz not null default now(),
  released_at timestamptz,
  constraint training_archive_manifest_pins_key_check
    check (pin_key ~ '^[A-Za-z0-9_.:/-]{1,160}$'),
  constraint training_archive_manifest_pins_reason_check
    check (reason is null or char_length(reason) <= 500),
  constraint training_archive_manifest_pins_release_check
    check (released_at is null or released_at >= created_at)
);

create index if not exists training_archive_manifest_pins_active_manifest_idx
  on public.training_archive_manifest_pins(manifest_id)
  where released_at is null;

alter table public.training_archive_manifest_pins enable row level security;

revoke all on table public.training_archive_manifest_pins
  from public, anon, authenticated;
grant select, insert, update, delete on table public.training_archive_manifest_pins
  to service_role;

create or replace function public.training_archive_retention_preview(
  p_keep_latest integer default 2
)
returns table (
  keep_latest integer,
  complete_manifests bigint,
  active_pins bigint,
  pinned_manifests bigint,
  retained_complete_manifests bigint,
  expirable_complete_manifests bigint,
  eventual_reclaimable_objects bigint,
  eventual_reclaimable_bytes bigint
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  if p_keep_latest < 2 or p_keep_latest > 100 then
    raise exception 'p_keep_latest must be between 2 and 100';
  end if;

  return query
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

    -- Never make objects referenced by an in-flight/non-complete manifest
    -- eligible for reclamation in preview.
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
    p_keep_latest,
    (select count(*) from ranked_complete)::bigint,
    (select count(*) from active_pin_rows)::bigint,
    (select count(*) from active_pinned_manifests)::bigint,
    (select count(*) from retained_complete)::bigint,
    (
      select count(*)
      from ranked_complete c
      left join retained_complete r on r.manifest_id = c.manifest_id
      where r.manifest_id is null
    )::bigint,
    (select count(*) from eventual_candidates)::bigint,
    (select coalesce(sum(size_bytes), 0) from eventual_candidates)::bigint;
end;
$$;

revoke all on function public.training_archive_retention_preview(integer)
  from public, anon, authenticated;
grant execute on function public.training_archive_retention_preview(integer)
  to service_role;
