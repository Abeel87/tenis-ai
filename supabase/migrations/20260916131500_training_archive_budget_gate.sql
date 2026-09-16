-- Fail-closed storage budget gate for durable training archive manifests.
-- This is archive infrastructure only. It does not change model math, training,
-- Player DNA, Surface Elo, Symphony, Neuron, PLAYABLE, settlement, SHADOW/PROD
-- or iNeed$ calculations.
--
-- Supabase Free currently includes 1 GB file storage. The archive is capped at
-- 250 MB reserved bytes, while archive writes are also blocked once worst-case
-- project-accounted storage would exceed 750 MB. This keeps at least 250 MB of
-- provider-quota headroom for runtime growth/rollbacks and other buckets.
--
-- The guard is deliberately conservative: expected_unique_bytes is treated as
-- fully new at manifest start even though SHA-256 deduplication usually reuses
-- most objects. A rejected manifest therefore creates no archive entries,
-- object reservations or signed upload URLs.

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
  v_worst_case_new_bytes bigint := 0;
  v_projected_archive_bytes bigint := 0;
  v_projected_project_bytes bigint := 0;
  c_archive_budget_bytes constant bigint := 250000000;
  c_project_archive_write_ceiling_bytes constant bigint := 750000000;
begin
  if new.status <> 'staged' then
    return new;
  end if;

  v_worst_case_new_bytes := coalesce(new.expected_unique_bytes, 0);
  if v_worst_case_new_bytes < 0 then
    raise exception 'training archive expected_unique_bytes must be non-negative';
  end if;

  -- Rows in training_archive_objects are reservations even if a previous upload
  -- was interrupted before the physical Storage object was confirmed.
  select coalesce(sum(o.size_bytes), 0)
    into v_archive_reserved_bytes
  from public.training_archive_objects o;

  select coalesce(sum(coalesce((s.metadata ->> 'size')::bigint, 0)), 0)
    into v_project_physical_bytes
  from storage.objects s;

  -- Add reserved archive bytes that are not yet represented in physical Storage
  -- so an interrupted publisher cannot make the project budget look smaller.
  select coalesce(sum(o.size_bytes), 0)
    into v_archive_missing_reserved_bytes
  from public.training_archive_objects o
  left join storage.objects s
    on s.bucket_id = 'tenis-ai-training-archive-private'
   and s.name = o.storage_path
  where s.id is null;

  v_project_accounted_bytes := v_project_physical_bytes + v_archive_missing_reserved_bytes;
  v_projected_archive_bytes := v_archive_reserved_bytes + v_worst_case_new_bytes;
  v_projected_project_bytes := v_project_accounted_bytes + v_worst_case_new_bytes;

  if v_projected_archive_bytes > c_archive_budget_bytes then
    raise exception using
      errcode = 'P0001',
      message = format(
        'training archive budget exceeded: projected archive bytes %s > %s',
        v_projected_archive_bytes,
        c_archive_budget_bytes
      );
  end if;

  if v_projected_project_bytes > c_project_archive_write_ceiling_bytes then
    raise exception using
      errcode = 'P0001',
      message = format(
        'training archive project storage ceiling exceeded: projected accounted bytes %s > %s',
        v_projected_project_bytes,
        c_project_archive_write_ceiling_bytes
      );
  end if;

  return new;
end;
$$;

revoke all on function public.training_archive_enforce_budget()
  from public, anon, authenticated;
grant execute on function public.training_archive_enforce_budget()
  to service_role;

drop trigger if exists training_archive_manifest_budget_gate
  on public.training_archive_manifests;
create trigger training_archive_manifest_budget_gate
before insert on public.training_archive_manifests
for each row
execute function public.training_archive_enforce_budget();
